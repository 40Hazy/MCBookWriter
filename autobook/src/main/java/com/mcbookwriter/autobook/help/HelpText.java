package com.mcbookwriter.autobook.help;

import net.fabricmc.loader.api.FabricLoader;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * AutoBook 帮助文本。命令 /autobook help 与游戏内说明页共用同一份内容。
 */
public final class HelpText {
    private static final Map<String, List<String>> TOPICS = new LinkedHashMap<>();

    static {
        TOPICS.put("start", List.of(
            "开始任务",
            "",
            "1. 将 job.json 放入 autobook/jobs/",
            "2. /autobook add <任务名>",
            "3. /autobook start",
            "4. /autobook list 或 status 查看进度",
            "",
            "单任务：/autobook start 三体1",
            "多任务：add 三体1、add 西游记，再 start",
            "准备足够的空的书与笔；运行中关闭背包等界面"
        ));
        TOPICS.put("run", List.of(
            "运行与任务状态",
            "",
            "运行：CREATED->PLANNING->QUEUING->RUNNING<->PAUSED->COMPLETED",
            "      RUNNING 可转 FAILED 或 CANCELLED",
            "任务：PENDING->QUEUED->RUNNING<->PAUSED->COMPLETED",
            "      失败为 FAILED，取消为 CANCELLED",
            "",
            "QUEUING  已准备好，等待 start",
            "RUNNING  正在写入；完成一本自动进入下一本",
            "PAUSED   可 resume 恢复",
            "COMPLETED 全部结束；FAILED 需 retry",
            "CANCELLED stop 或取消后的终态",
            "",
            "运行中也可以继续 add，新任务排在当前任务之后"
        ));
        TOPICS.put("job", List.of(
            "任务文件",
            "",
            "路径：autobook/jobs/<任务名>.json",
            "命令使用不含 .json 的任务名，支持中文",
            "",
            "job 由 BookForge 生成，GUI 也可直接安装",
            "修改 job 内容或 options 会改变 planHash，该任务会从头开始",
            "默认 skipExistingBooks=true，会跳过已签名的同名同页数成书"
        ));
        TOPICS.put("cancel", List.of(
            "暂停、取消、终止与移除",
            "",
            "pause    可恢复暂停；当前书完成后生效",
            "cancel   只取消当前或指定任务，运行继续下一个",
            "stop     终止整条运行（CANCELLED），进度文件保留",
            "remove   移除未开始或已结束的任务记录",
            "retry    把 FAILED/CANCELLED 任务重新入队",
            "",
            "RUNNING/PAUSED 的任务不能直接 remove，需先 cancel",
            "stop 之后可用 /autobook start <任务名> 重新开始"
        ));
        TOPICS.put("config", List.of(
            "配置",
            "",
            "/autobook ui                         打开图形配置界面",
            "/autobook config                     查看全部配置",
            "/autobook config <key> <value>       修改并保存",
            "",
            "常用项：pageLimit、breakAtSentence、verifyContent、",
            "        autoRecover、queueStopOnFailure、节奏 tick",
            "配置在下一次 plan/start 时生效；运行中的计划不变"
        ));
        TOPICS.put("verify", List.of(
            "内容校验",
            "",
            "签名后逐页比对计划文本与成书页，并输出整书 SHA-256",
            "页数或内容不一致时进入 VERIFY 暂停，不推进进度",
            "",
            "处理：移除问题书后 /autobook resume",
            "关闭：/autobook config verifyContent false",
            "日志会记录 expected/actual sha256 与首个不一致页"
        ));
        TOPICS.put("recover", List.of(
            "暂停与恢复",
            "",
            "SUPPLY  缺少空的书与笔；补给后每 20 tick 自动检测并继续",
            "CONFIRM 服务器未确认：右键打开并关闭该书，再 /autobook resume",
            "VERIFY  内容校验失败：移除问题书后 resume",
            "MANUAL  人工暂停或空书无法就位：整理后 resume",
            "",
            "连续失败会先自动恢复一轮：长等待并打开/关闭书本页面",
            "仍失败才进入 CONFIRM，等待人工处理"
        ));
    }

    private HelpText() {
    }

    public static String version() {
        try {
            return FabricLoader.getInstance().getModContainer("autobook")
                .map(container -> container.getMetadata().getVersion().getFriendlyString())
                .orElse("dev");
        } catch (RuntimeException | LinkageError error) {
            return "dev";
        }
    }

    public static List<String> lines() {
        List<String> lines = new ArrayList<>();
        lines.add("AutoBook " + version());
        lines.add("");
        lines.add("首次使用");
        lines.add("  1. 将 job 放入 autobook/jobs/");
        lines.add("  2. /autobook add <任务名>");
        lines.add("  3. /autobook start");
        lines.add("  4. /autobook list 或 status 查看");
        lines.add("");
        lines.add("命令");
        lines.add("  /autobook plan <任务>      只预演，不改变运行");
        lines.add("  /autobook add <任务>       加入当前运行，可多次");
        lines.add("  /autobook start [任务]     启动；带任务=add+start");
        lines.add("  /autobook list / status    查看运行与任务状态");
        lines.add("  /autobook pause / resume   可恢复暂停");
        lines.add("  /autobook cancel [任务]    取消任务，运行继续下一个");
        lines.add("  /autobook stop             终止整条运行(CANCELLED)");
        lines.add("  /autobook remove <任务>    移除未开始/已结束任务");
        lines.add("  /autobook retry <任务>     失败/取消后重新入队");
        lines.add("  /autobook ui / config      图形界面 / 配置命令");
        lines.add("");
        lines.add("更多主题：/autobook help <主题>");
        lines.add("  start run job cancel config verify recover");
        return lines;
    }

    public static List<String> topicLines(String topic) {
        if (topic == null || topic.isBlank()) {
            return lines();
        }
        String key = normalize(topic);
        List<String> lines = TOPICS.get(key);
        return lines == null ? null : lines;
    }

    public static String topicList() {
        return String.join(", ", TOPICS.keySet());
    }

    private static String normalize(String topic) {
        String key = topic.trim().toLowerCase(Locale.ROOT);
        return switch (key) {
            case "开始", "起步" -> "start";
            case "运行", "状态" -> "run";
            case "任务" -> "job";
            case "取消", "停止", "终止", "移除" -> "cancel";
            case "配置", "设置" -> "config";
            case "校验", "验证" -> "verify";
            case "恢复", "暂停" -> "recover";
            default -> key;
        };
    }
}
