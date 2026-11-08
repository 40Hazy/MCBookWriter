package com.mcbookwriter.autobook.run;

import com.mcbookwriter.autobook.AutoBookClient;
import com.mcbookwriter.autobook.config.AutoBookConfig;
import com.mcbookwriter.autobook.job.JobRunner;
import com.mcbookwriter.autobook.layout.PlannedBook;
import com.mcbookwriter.autobook.progress.PlanDigest;
import com.mcbookwriter.autobook.progress.StateStore;
import com.mcbookwriter.autobook.writer.BookWriter;
import net.minecraft.client.Minecraft;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.List;

/**
 * 唯一的运行流水线：单本只是包含一个任务的 Run。
 */
public final class RunRunner {
    private static final RunRunner INSTANCE = new RunRunner();

    private final RunStore store = RunStore.defaultStore();
    private final StateStore stateStore = StateStore.defaultStore();
    private RunState state;
    private boolean armed;

    private RunRunner() {
    }

    public static RunRunner get() {
        return INSTANCE;
    }

    public RunState state() {
        if (state == null) {
            state = load();
        }
        return state;
    }

    public boolean active() {
        return RunState.RUN_RUNNING.equals(state().status)
            || RunState.RUN_PAUSED.equals(state().status);
    }

    public List<RunJob> jobs() {
        return state().jobs;
    }

    public RunJob add(String jobName) throws IOException {
        String name = requireName(jobName);
        RunState run = state();
        if (isTerminalRun(run.status)) {
            resetForNewRun(run);
        }
        boolean activeRun = RunState.RUN_RUNNING.equals(run.status)
            || RunState.RUN_PAUSED.equals(run.status);
        if (!activeRun
            && !RunState.RUN_CREATED.equals(run.status)
            && !RunState.RUN_PLANNING.equals(run.status)
            && !RunState.RUN_QUEUING.equals(run.status)) {
            throw new IllegalStateException("运行正在进行，请先 /autobook stop 或等待完成");
        }

        RunJob job = run.append(name);
        if (!activeRun) {
            run.status = RunState.RUN_PLANNING;
        }
        save();

        try {
            planJob(job);
            if (!activeRun) {
                run.status = RunState.RUN_QUEUING;
                run.reason = "";
            }
            save();
            AutoBookClient.LOG.info(
                "AutoBook: run {} job '{}' ({} books, {} pages)",
                RunState.label(run.status),
                job.name,
                job.totalBooks,
                job.totalPages
            );
            return job;
        } catch (Exception error) {
            job.status = RunState.JOB_FAILED;
            job.error = message(error);
            job.finishedAt = now();
            if (!activeRun) {
                run.status = run.hasQueued() ? RunState.RUN_QUEUING : RunState.RUN_FAILED;
                run.reason = job.error;
            }
            save();
            AutoBookClient.LOG.warn("AutoBook: run could not plan '{}': {}", job.name, job.error);
            throw error instanceof IOException io
                ? io
                : new IOException(job.error, error);
        }
    }

    public void start() throws IOException {
        RunState run = state();
        BookWriter writer = BookWriter.get();
        BookWriter.Progress progress = writer.progress();

        if (RunState.RUN_PAUSED.equals(run.status)) {
            throw new IllegalStateException("运行已暂停，请使用 /autobook resume");
        }
        if (RunState.RUN_RUNNING.equals(run.status)) {
            throw new IllegalStateException("运行已经在进行中");
        }
        if (!RunState.RUN_QUEUING.equals(run.status)) {
            throw new IllegalStateException("没有待启动的任务，请先 /autobook add <任务名>");
        }
        RunJob job = run.current();
        if (job == null || !RunState.isQueued(job.status)) {
            throw new IllegalStateException("没有待执行的任务，请先 /autobook add <任务名>");
        }

        if (progress.state() == BookWriter.State.PAUSED && job.name.equals(progress.jobName())) {
            writer.resume();
            job.status = RunState.JOB_RUNNING;
            run.status = RunState.RUN_RUNNING;
            armed = false;
            save();
            return;
        }
        if (progress.state() != BookWriter.State.IDLE) {
            writer.stop();
        }

        run.status = RunState.RUN_RUNNING;
        run.reason = "";
        job.status = RunState.JOB_QUEUED;
        armed = true;
        save();
        AutoBookClient.LOG.info(
            "AutoBook: run started ({} jobs, current '{}')",
            run.jobs.size(),
            job.name
        );
    }

    /**
     * 可恢复暂停。返回给命令行的状态说明。
     */
    public String pause() throws IOException {
        RunState run = state();
        if (!RunState.RUN_RUNNING.equals(run.status)) {
            throw new IllegalStateException("当前运行不在 RUNNING 状态");
        }
        RunJob job = run.current();
        BookWriter writer = BookWriter.get();
        BookWriter.Progress progress = writer.progress();
        if (progress.state() == BookWriter.State.IDLE) {
            run.status = RunState.RUN_PAUSED;
            armed = false;
            save();
            return "已暂停，可用 /autobook resume 继续";
        }
        if (!writer.pause()) {
            throw new IllegalStateException("当前没有可暂停的任务");
        }
        if (writer.progress().state() == BookWriter.State.PAUSED) {
            run.status = RunState.RUN_PAUSED;
            if (job != null) {
                job.status = RunState.JOB_PAUSED;
            }
            save();
            return "已暂停，可用 /autobook resume 继续";
        }
        save();
        return "将在当前书完成后暂停";
    }

    public void resume() throws IOException {
        RunState run = state();
        if (!RunState.RUN_PAUSED.equals(run.status)) {
            throw new IllegalStateException("当前运行不在 PAUSED 状态");
        }
        RunJob job = run.current();
        if (job == null) {
            throw new IllegalStateException("没有可继续的任务");
        }
        BookWriter writer = BookWriter.get();
        BookWriter.Progress progress = writer.progress();
        boolean samePausedJob = progress.state() == BookWriter.State.PAUSED
            && job.name.equals(progress.jobName());
        if (samePausedJob) {
            if (!writer.resume()) {
                throw new IllegalStateException("无法继续当前书本");
            }
            job.status = RunState.JOB_RUNNING;
            armed = false;
        } else {
            job.status = RunState.JOB_QUEUED;
            armed = true;
        }
        run.status = RunState.RUN_RUNNING;
        save();
    }

    public RunJob cancel(String jobName) throws IOException {
        RunState run = state();
        RunJob job;
        if (jobName == null || jobName.isBlank()) {
            job = run.current();
        } else {
            RunJob active = run.findNonTerminal(jobName);
            job = active != null ? active : run.find(jobName);
        }
        if (job == null) {
            throw new IllegalStateException(jobName == null || jobName.isBlank()
                ? "当前没有可取消的任务"
                : "未找到任务: " + jobName);
        }
        if (RunState.isTerminal(job.status)) {
            throw new IllegalStateException("任务已结束: " + job.name);
        }

        boolean wasCurrent = job == run.current();
        String previousStatus = run.status;
        if (wasCurrent) {
            BookWriter writer = BookWriter.get();
            if (!(writer.progress().state() == BookWriter.State.IDLE
                || writer.progress().state() == BookWriter.State.DONE)) {
                writer.stop();
            }
        }
        job.status = RunState.JOB_CANCELLED;
        job.finishedAt = now();
        job.error = "已取消";
        armed = false;

        if (wasCurrent) {
            run.currentIndex = run.currentIndex + 1;
            run.normalize();
            RunJob next = run.current();
            if (next == null) {
                run.status = RunState.RUN_CANCELLED;
                run.reason = "任务已取消";
            } else if (RunState.RUN_RUNNING.equals(previousStatus)) {
                run.status = RunState.RUN_RUNNING;
                armed = true;
            } else if (RunState.RUN_PAUSED.equals(previousStatus)) {
                run.status = RunState.RUN_PAUSED;
            } else {
                run.status = RunState.RUN_QUEUING;
            }
        } else if (RunState.RUN_QUEUING.equals(run.status) && !run.hasQueued()) {
            run.status = RunState.RUN_CANCELLED;
            run.reason = "任务已取消";
        }
        save();
        AutoBookClient.LOG.info("AutoBook: run cancelled job '{}'", job.name);
        return job;
    }

    public void stop() throws IOException {
        RunState run = state();
        if (isTerminalRun(run.status)) {
            throw new IllegalStateException("运行已结束");
        }
        BookWriter writer = BookWriter.get();
        if (!(writer.progress().state() == BookWriter.State.IDLE
            || writer.progress().state() == BookWriter.State.DONE)) {
            writer.stop();
        }
        String stamp = now();
        for (RunJob job : run.jobs) {
            if (job != null && !RunState.isTerminal(job.status)) {
                job.status = RunState.JOB_CANCELLED;
                job.finishedAt = stamp;
                job.error = "运行已终止";
            }
        }
        run.status = RunState.RUN_CANCELLED;
        run.reason = "用户终止运行";
        armed = false;
        save();
        AutoBookClient.LOG.info("AutoBook: run stopped by user");
    }

    /**
     * 兼容旧 /autobook queue clear：终止运行并清空任务列表。
     */
    public void clear() throws IOException {
        RunState run = state();
        BookWriter writer = BookWriter.get();
        if (!(writer.progress().state() == BookWriter.State.IDLE
            || writer.progress().state() == BookWriter.State.DONE)) {
            writer.stop();
        }
        String stamp = now();
        for (RunJob job : run.jobs) {
            if (job != null && !RunState.isTerminal(job.status)) {
                job.status = RunState.JOB_CANCELLED;
                job.finishedAt = stamp;
                job.error = "队列已清空";
            }
        }
        run.jobs.clear();
        run.currentIndex = 0;
        run.status = RunState.RUN_CANCELLED;
        run.reason = "队列已清空";
        armed = false;
        save();
        AutoBookClient.LOG.info("AutoBook: run cleared");
    }

    public RunJob remove(String jobName) throws IOException {
        RunState run = state();
        RunJob removed = run.remove(requireName(jobName));
        if (removed == null) {
            throw new IllegalStateException("未找到任务: " + jobName);
        }
        if (RunState.RUN_QUEUING.equals(run.status) && !run.hasQueued()) {
            run.status = RunState.RUN_CANCELLED;
            run.reason = "任务已移除";
        }
        save();
        AutoBookClient.LOG.info("AutoBook: run removed job '{}'", removed.name);
        return removed;
    }

    public RunJob retry(String jobName) throws IOException {
        String name = requireName(jobName);
        RunState run = state();
        RunJob job = run.findEnded(name);
        if (job == null) {
            if (run.find(name) != null) {
                throw new IllegalStateException("只能重试失败或已取消的任务: " + name);
            }
            throw new IllegalStateException("未找到任务: " + name);
        }
        for (RunJob other : run.jobs) {
            if (other != null && other != job && name.equals(other.name) && !RunState.isTerminal(other.status)) {
                throw new IllegalStateException("已有同名的活动任务: " + name);
            }
        }

        int oldIndex = indexOf(run, job);
        if (oldIndex < run.currentIndex) {
            run.currentIndex--;
        }
        run.jobs.remove(oldIndex);
        run.jobs.add(job);

        job.status = RunState.JOB_PENDING;
        job.error = "";
        job.finishedAt = "";
        job.startedAt = "";
        job.nextIndex = 0;
        job.completedBooks = 0;
        job.totalBooks = 0;
        job.totalPages = 0;
        job.verifiedBooks = 0;
        try {
            planJob(job);
        } catch (Exception error) {
            job.status = RunState.JOB_FAILED;
            job.error = message(error);
            job.finishedAt = now();
            if (isTerminalRun(run.status)) {
                run.status = RunState.RUN_FAILED;
            }
            save();
            throw error instanceof IOException io ? io : new IOException(job.error, error);
        }

        if (isTerminalRun(run.status)) {
            run.status = RunState.RUN_QUEUING;
            run.reason = "";
            run.currentIndex = indexOf(run, job);
        } else if (RunState.RUN_QUEUING.equals(run.status) && run.current() == null) {
            run.currentIndex = indexOf(run, job);
        }
        save();
        AutoBookClient.LOG.info("AutoBook: run retried job '{}'", job.name);
        return job;
    }

    public void tick(Minecraft client) {
        RunState run = state();
        if (!RunState.RUN_RUNNING.equals(run.status)) {
            return;
        }
        RunJob job = run.current();
        if (job == null) {
            finishOrAdvance(run, RunState.RUN_COMPLETED);
            return;
        }

        BookWriter.Progress progress = BookWriter.get().progress();
        switch (progress.state()) {
            case IDLE -> {
                if (armed) {
                    startCurrent(run, job);
                }
            }
            case DONE -> {
                if (job.name.equals(progress.jobName())) {
                    completeCurrent(run, job, progress);
                } else if (armed) {
                    startCurrent(run, job);
                }
            }
            case ERROR -> {
                if (job.name.equals(progress.jobName())) {
                    failCurrent(run, job, BookWriter.get().status());
                } else if (armed) {
                    startCurrent(run, job);
                }
            }
            case PAUSED -> {
                if (job.name.equals(progress.jobName())) {
                    job.status = RunState.JOB_PAUSED;
                    run.status = RunState.RUN_PAUSED;
                    armed = false;
                    saveQuietly();
                }
            }
            default -> updateProgress(run, job, progress);
        }
    }

    public String describe() {
        RunState run = state();
        if (run.jobs.isEmpty()) {
            return "运行 " + RunState.label(run.status) + "：没有任务";
        }
        StringBuilder builder = new StringBuilder();
        builder.append("运行 ").append(RunState.label(run.status))
            .append("（").append(run.jobs.size()).append(" 个任务）");
        if (!run.reason.isBlank()) {
            builder.append(" - ").append(run.reason);
        }
        builder.append('\n');
        int index = 0;
        for (RunJob job : run.jobs) {
            builder.append(index == run.currentIndex ? "> " : "  ")
                .append(index + 1).append(". ").append(job.name)
                .append(" [").append(RunState.jobLabel(job.status)).append("]");
            if (job.totalBooks > 0) {
                builder.append(" ").append(job.completedBooks).append("/").append(job.totalBooks).append(" 本");
                if (job.verifiedBooks > 0) {
                    builder.append(", 校验 ").append(job.verifiedBooks);
                }
            } else if (job.totalPages > 0) {
                builder.append(" ").append(job.totalPages).append(" 页");
            }
            if (job.error != null && !job.error.isBlank()
                && !RunState.JOB_CANCELLED.equals(job.status)) {
                builder.append(" - ").append(job.error);
            }
            builder.append('\n');
            index++;
        }
        return builder.toString().trim();
    }

    public String statusText() {
        RunState run = state();
        RunJob job = run.current();
        if (job == null) {
            return "运行 " + RunState.label(run.status);
        }
        StringBuilder builder = new StringBuilder("运行 ").append(RunState.label(run.status))
            .append("，任务 ").append(job.name)
            .append(" [").append(RunState.jobLabel(job.status)).append("]");
        if (job.totalBooks > 0) {
            builder.append("，第 ").append(Math.min(job.nextIndex + 1, job.totalBooks))
                .append("/").append(job.totalBooks).append(" 本");
        }
        if (job.totalPages > 0) {
            builder.append("，共 ").append(job.totalPages).append(" 页");
        }
        if (job.verifiedBooks > 0) {
            builder.append("，已验证 ").append(job.verifiedBooks).append(" 本");
        }
        if (!run.reason.isBlank()) {
            builder.append(" - ").append(run.reason);
        }
        return builder.toString();
    }

    private void startCurrent(RunState run, RunJob job) {
        armed = false;
        job.status = RunState.JOB_RUNNING;
        job.startedAt = job.startedAt.isBlank() ? now() : job.startedAt;
        saveQuietly();

        try {
            JobRunner.Prepared prepared = JobRunner.prepare(job.name);
            if (prepared.books().isEmpty()) {
                throw new IllegalArgumentException("计划为空");
            }
            String hash = PlanDigest.hash(job.name, prepared.books());
            job.planHash = hash;
            job.totalBooks = prepared.books().size();
            job.totalPages = prepared.books().stream().mapToInt(book -> book.pages().size()).sum();

            var restored = stateStore.load(hash);
            if (restored != null && restored.nextIndex >= prepared.books().size()) {
                job.status = RunState.JOB_COMPLETED;
                job.completedBooks = prepared.books().size();
                job.nextIndex = prepared.books().size();
                job.verifiedBooks = restored.verifiedBooks;
                job.finishedAt = now();
                job.error = "";
                saveQuietly();
                AutoBookClient.LOG.info(
                    "AutoBook: run job '{}' already finished, skipping",
                    job.name
                );
                finishOrAdvance(run, RunState.RUN_COMPLETED);
                return;
            }
            boolean resume = restored != null
                && restored.nextIndex > 0
                && restored.nextIndex < prepared.books().size();
            BookWriter.get().start(
                job.name,
                prepared.job().sourceHash,
                prepared.books(),
                resume,
                prepared.settings().verifyContent()
            );
            job.nextIndex = resume ? restored.nextIndex : 0;
            job.completedBooks = resume ? restored.completedBooks : 0;
            job.verifiedBooks = resume ? restored.verifiedBooks : 0;
            job.error = "";
            saveQuietly();
            AutoBookClient.LOG.info(
                "AutoBook: run started '{}' ({}/{}){}",
                job.name,
                indexOf(run, job) + 1,
                run.jobs.size(),
                resume ? " resume" : ""
            );
        } catch (Exception error) {
            failCurrent(run, job, message(error));
        }
    }

    private void completeCurrent(RunState run, RunJob job, BookWriter.Progress progress) {
        job.status = RunState.JOB_COMPLETED;
        job.completedBooks = progress.completedBooks() > 0 ? progress.completedBooks() : job.totalBooks;
        job.totalBooks = progress.totalBooks() > 0 ? progress.totalBooks() : job.totalBooks;
        job.nextIndex = progress.nextIndex();
        job.verifiedBooks = progress.verifiedBooks();
        job.finishedAt = now();
        job.error = "";
        AutoBookClient.LOG.info("AutoBook: run completed job '{}'", job.name);
        BookWriter.get().stop();
        finishOrAdvance(run, RunState.RUN_COMPLETED);
    }

    private void failCurrent(RunState run, RunJob job, String reason) {
        job.status = RunState.JOB_FAILED;
        job.error = reason == null || reason.isBlank() ? "未知失败" : reason;
        job.finishedAt = now();
        AutoBookClient.LOG.warn("AutoBook: run job '{}' failed: {}", job.name, job.error);

        BookWriter.Progress progress = BookWriter.get().progress();
        if (!(progress.state() == BookWriter.State.IDLE || progress.state() == BookWriter.State.DONE)) {
            BookWriter.get().stop();
        }
        if (AutoBookConfig.get().queueStopOnFailure) {
            run.status = RunState.RUN_FAILED;
            run.reason = job.error;
            armed = false;
            saveQuietly();
            AutoBookClient.LOG.warn(
                "AutoBook: run stopped after failure ({}), fix and /autobook retry {}",
                job.error,
                job.name
            );
            return;
        }
        finishOrAdvance(run, RunState.RUN_COMPLETED);
    }

    /**
     * 推进到下一个未终止任务；没有则按指定的终止状态结束运行。
     */
    private void finishOrAdvance(RunState run, String finalStatus) {
        int next = run.nextQueuedIndex(run.currentIndex + 1);
        if (next >= 0) {
            run.currentIndex = next;
            run.status = RunState.RUN_RUNNING;
            run.reason = "";
            armed = true;
            saveQuietly();
            return;
        }
        run.status = finalStatus;
        armed = false;
        if (RunState.RUN_COMPLETED.equals(finalStatus)) {
            run.reason = "";
        }
        saveQuietly();
        AutoBookClient.LOG.info("AutoBook: run finished ({})", RunState.label(run.status));
    }

    private void updateProgress(RunState run, RunJob job, BookWriter.Progress progress) {
        if (!job.name.equals(progress.jobName())) {
            return;
        }
        boolean changed = false;
        if (job.nextIndex != progress.nextIndex()) {
            job.nextIndex = progress.nextIndex();
            changed = true;
        }
        if (job.totalBooks != progress.totalBooks()) {
            job.totalBooks = progress.totalBooks();
            changed = true;
        }
        if (job.completedBooks != progress.completedBooks()) {
            job.completedBooks = progress.completedBooks();
            changed = true;
        }
        if (job.verifiedBooks != progress.verifiedBooks()) {
            job.verifiedBooks = progress.verifiedBooks();
            changed = true;
        }
        if (run.status != RunState.RUN_RUNNING) {
            run.status = RunState.RUN_RUNNING;
            changed = true;
        }
        if (job.status != RunState.JOB_RUNNING) {
            job.status = RunState.JOB_RUNNING;
            changed = true;
        }
        if (changed) {
            saveQuietly();
        }
    }

    private void planJob(RunJob job) throws IOException {
        JobRunner.Prepared prepared = JobRunner.prepare(job.name);
        if (prepared.books().isEmpty()) {
            throw new IllegalArgumentException("计划为空");
        }
        List<PlannedBook> books = prepared.books();
        job.totalBooks = books.size();
        job.totalPages = books.stream().mapToInt(book -> book.pages().size()).sum();
        job.planHash = PlanDigest.hash(job.name, books);
        job.status = RunState.JOB_QUEUED;
        job.error = "";
        job.finishedAt = "";
        job.startedAt = "";
    }

    private RunState load() {
        try {
            RunState loaded = store.load();
            state = loaded;
            recover(loaded);
            return loaded;
        } catch (IOException error) {
            AutoBookClient.LOG.warn("AutoBook: failed to read run.json: {}", error.getMessage());
            return new RunState();
        }
    }

    /**
     * 重启后不自动开写：运行中的任务恢复为暂停，等待手动 resume。
     */
    private void recover(RunState run) {
        run.normalize();
        boolean changed = false;
        for (RunJob job : run.jobs) {
            if (job == null) {
                continue;
            }
            if (RunState.JOB_PENDING.equals(job.status)) {
                job.status = RunState.JOB_QUEUED;
                changed = true;
            }
            if (RunState.JOB_RUNNING.equals(job.status) && !RunState.RUN_RUNNING.equals(run.status)) {
                job.status = RunState.JOB_PAUSED;
                changed = true;
            }
        }
        if (RunState.RUN_PLANNING.equals(run.status) || RunState.RUN_CREATED.equals(run.status)) {
            if (run.hasQueued()) {
                run.status = RunState.RUN_QUEUING;
                changed = true;
            }
        } else if (RunState.RUN_RUNNING.equals(run.status)) {
            run.status = run.hasQueued() || run.current() != null
                ? RunState.RUN_PAUSED
                : RunState.RUN_COMPLETED;
            changed = true;
        }
        if (RunState.RUN_PAUSED.equals(run.status)) {
            for (RunJob job : run.jobs) {
                if (job != null && RunState.JOB_RUNNING.equals(job.status)) {
                    job.status = RunState.JOB_PAUSED;
                    changed = true;
                }
            }
        }
        if (changed) {
            saveQuietly();
        }
    }

    private void resetForNewRun(RunState run) {
        run.jobs.clear();
        run.currentIndex = 0;
        run.status = RunState.RUN_CREATED;
        run.reason = "";
        run.createdAt = now();
        armed = false;
    }

    private int indexOf(RunState run, RunJob job) {
        for (int index = 0; index < run.jobs.size(); index++) {
            if (run.jobs.get(index) == job) {
                return index;
            }
        }
        return 0;
    }

    private void save() throws IOException {
        state.updatedAt = now();
        store.save(state);
    }

    private void saveQuietly() {
        try {
            save();
        } catch (IOException error) {
            AutoBookClient.LOG.warn("AutoBook: failed to save run.json: {}", error.getMessage());
        }
    }

    private static boolean isTerminalRun(String status) {
        return RunState.RUN_COMPLETED.equals(status)
            || RunState.RUN_FAILED.equals(status)
            || RunState.RUN_CANCELLED.equals(status);
    }

    private static String requireName(String jobName) {
        if (jobName == null || jobName.isBlank()) {
            throw new IllegalArgumentException("请提供任务名");
        }
        return jobName.trim();
    }

    private static String now() {
        return OffsetDateTime.now().toString();
    }

    private static String message(Throwable error) {
        String text = error.getMessage();
        return text == null || text.isBlank() ? error.getClass().getSimpleName() : text;
    }
}
