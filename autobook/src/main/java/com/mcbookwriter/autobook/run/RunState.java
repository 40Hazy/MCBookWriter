package com.mcbookwriter.autobook.run;

import java.util.ArrayList;
import java.util.List;

/**
 * 一次运行（Run）的持久化状态，保存到 autobook/run.json。
 *
 * <p>运行状态：created → planning → queuing → running ⇄ paused → completed，
 * 另有 failed / cancelled 两个终止分支。</p>
 */
public class RunState {
    public static final String RUN_CREATED = "created";
    public static final String RUN_PLANNING = "planning";
    public static final String RUN_QUEUING = "queuing";
    public static final String RUN_RUNNING = "running";
    public static final String RUN_PAUSED = "paused";
    public static final String RUN_COMPLETED = "completed";
    public static final String RUN_FAILED = "failed";
    public static final String RUN_CANCELLED = "cancelled";

    public static final String JOB_PENDING = "pending";
    public static final String JOB_QUEUED = "queued";
    public static final String JOB_RUNNING = "running";
    public static final String JOB_PAUSED = "paused";
    public static final String JOB_COMPLETED = "completed";
    public static final String JOB_FAILED = "failed";
    public static final String JOB_CANCELLED = "cancelled";

    public int version = 2;
    public String status = RUN_CREATED;
    public int currentIndex;
    public List<RunJob> jobs = new ArrayList<>();
    public String reason = "";
    public String createdAt = "";
    public String updatedAt = "";

    public RunJob current() {
        if (jobs == null || currentIndex < 0 || currentIndex >= jobs.size()) {
            return null;
        }
        return jobs.get(currentIndex);
    }

    public RunJob find(String name) {
        if (jobs == null || name == null) {
            return null;
        }
        for (RunJob job : jobs) {
            if (job != null && name.equals(job.name)) {
                return job;
            }
        }
        return null;
    }

    public boolean hasActiveName(String name) {
        return findNonTerminal(name) != null;
    }

    public RunJob findNonTerminal(String name) {
        if (jobs == null) {
            return null;
        }
        for (RunJob job : jobs) {
            if (job != null && name.equals(job.name) && !isTerminal(job.status)) {
                return job;
            }
        }
        return null;
    }

    public RunJob findEnded(String name) {
        if (jobs == null) {
            return null;
        }
        for (RunJob job : jobs) {
            if (job != null && name.equals(job.name)
                && (JOB_FAILED.equals(job.status) || JOB_CANCELLED.equals(job.status))) {
                return job;
            }
        }
        return null;
    }

    public RunJob append(String name) {
        if (jobs == null) {
            jobs = new ArrayList<>();
        }
        if (hasActiveName(name)) {
            throw new IllegalArgumentException("任务已在运行中: " + name);
        }
        RunJob job = new RunJob();
        job.name = name;
        job.addedAt = java.time.OffsetDateTime.now().toString();
        jobs.add(job);
        if (currentIndex < 0) {
            currentIndex = 0;
        }
        normalize();
        return job;
    }

    /**
     * 只允许移除尚未开始的任务；运行中/已暂停的任务必须先 cancel。
     */
    public RunJob remove(String name) {
        if (jobs == null) {
            return null;
        }
        for (int index = 0; index < jobs.size(); index++) {
            RunJob job = jobs.get(index);
            if (job == null || !name.equals(job.name)) {
                continue;
            }
            if (JOB_RUNNING.equals(job.status) || JOB_PAUSED.equals(job.status)) {
                throw new IllegalArgumentException("任务已开始，请先 cancel: " + name);
            }
            jobs.remove(index);
            if (index < currentIndex) {
                currentIndex--;
            }
            if (currentIndex < 0) {
                currentIndex = 0;
            }
            normalize();
            return job;
        }
        return null;
    }

    public boolean hasQueued() {
        if (jobs == null) {
            return false;
        }
        for (RunJob job : jobs) {
            if (job != null && (JOB_PENDING.equals(job.status) || JOB_QUEUED.equals(job.status))) {
                return true;
            }
        }
        return false;
    }

    public boolean allTerminal() {
        if (jobs == null || jobs.isEmpty()) {
            return true;
        }
        for (RunJob job : jobs) {
            if (job != null && !isTerminal(job.status)) {
                return false;
            }
        }
        return true;
    }

    public int nextQueuedIndex(int from) {
        if (jobs == null) {
            return -1;
        }
        for (int index = Math.max(0, from); index < jobs.size(); index++) {
            RunJob job = jobs.get(index);
            if (job != null && (JOB_PENDING.equals(job.status) || JOB_QUEUED.equals(job.status))) {
                return index;
            }
        }
        return -1;
    }

    /**
     * 跳过已完成/失败/取消的条目，把 currentIndex 指向第一个未终止任务。
     */
    public void normalize() {
        if (jobs == null) {
            jobs = new ArrayList<>();
        }
        if (currentIndex < 0) {
            currentIndex = 0;
        }
        while (currentIndex < jobs.size() && isTerminal(jobs.get(currentIndex).status)) {
            currentIndex++;
        }
        if (currentIndex > jobs.size()) {
            currentIndex = jobs.size();
        }
    }

    public void ensureDefaults() {
        if (jobs == null) {
            jobs = new ArrayList<>();
        }
        if (status == null || status.isBlank()) {
            status = RUN_CREATED;
        }
        if (reason == null) {
            reason = "";
        }
        for (RunJob job : jobs) {
            if (job == null) {
                continue;
            }
            if (job.status == null || job.status.isBlank()) {
                job.status = JOB_PENDING;
            }
            if (job.error == null) {
                job.error = "";
            }
            if (job.planHash == null) {
                job.planHash = "";
            }
            if (job.addedAt == null) {
                job.addedAt = "";
            }
            if (job.startedAt == null) {
                job.startedAt = "";
            }
            if (job.finishedAt == null) {
                job.finishedAt = "";
            }
        }
        if (currentIndex < 0) {
            currentIndex = 0;
        }
        if (currentIndex > jobs.size()) {
            currentIndex = jobs.size();
        }
    }

    public static boolean isTerminal(String status) {
        return JOB_COMPLETED.equals(status) || JOB_FAILED.equals(status) || JOB_CANCELLED.equals(status);
    }

    public static boolean isQueued(String status) {
        return JOB_PENDING.equals(status) || JOB_QUEUED.equals(status);
    }

    public static String label(String status) {
        return switch (status) {
            case RUN_CREATED -> "已创建";
            case RUN_PLANNING -> "准备中";
            case RUN_QUEUING -> "待启动";
            case RUN_RUNNING -> "运行中";
            case RUN_PAUSED -> "已暂停";
            case RUN_COMPLETED -> "已完成";
            case RUN_FAILED -> "失败";
            case RUN_CANCELLED -> "已取消";
            case JOB_PENDING -> "待准备";
            case JOB_QUEUED -> "待执行";
            default -> "执行中";
        };
    }

    public static String jobLabel(String status) {
        return switch (status) {
            case JOB_PENDING -> "待准备";
            case JOB_QUEUED -> "待执行";
            case JOB_RUNNING -> "执行中";
            case JOB_PAUSED -> "已暂停";
            case JOB_COMPLETED -> "已完成";
            case JOB_FAILED -> "失败";
            case JOB_CANCELLED -> "已取消";
            default -> status;
        };
    }
}
