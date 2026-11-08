package com.mcbookwriter.autobook.command;

import com.mcbookwriter.autobook.compat.ClientCommandsCompat;
import com.mcbookwriter.autobook.config.AutoBookConfig;
import com.mcbookwriter.autobook.gui.UiScreens;
import com.mcbookwriter.autobook.help.HelpText;
import com.mcbookwriter.autobook.job.JobRunner;
import com.mcbookwriter.autobook.layout.PlannedBook;
import com.mcbookwriter.autobook.run.RunJob;
import com.mcbookwriter.autobook.run.RunRunner;
import com.mcbookwriter.autobook.run.RunState;
import com.mcbookwriter.autobook.writer.BookWriter;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandRegistrationCallback;
import net.fabricmc.fabric.api.client.command.v2.FabricClientCommandSource;
import net.minecraft.network.chat.Component;

import java.io.IOException;
import java.util.List;

public final class AutoBookCommand {
    private AutoBookCommand() {
    }

    public static void register() {
        ClientCommandRegistrationCallback.EVENT.register(
            (dispatcher, registryAccess) -> register(dispatcher)
        );
    }

    public static void register(CommandDispatcher<FabricClientCommandSource> dispatcher) {
        dispatcher.register(
            ClientCommandsCompat.literal("autobook")
                .then(ClientCommandsCompat.literal("help")
                    .executes(context -> help(context.getSource(), null))
                    .then(ClientCommandsCompat.argument("topic", StringArgumentType.greedyString())
                        .executes(context -> help(
                            context.getSource(),
                            StringArgumentType.getString(context, "topic").trim()
                        ))))
                .then(ClientCommandsCompat.literal("plan")
                    .then(ClientCommandsCompat.argument("job", StringArgumentType.greedyString())
                        .executes(context -> plan(
                            context.getSource(),
                            StringArgumentType.getString(context, "job").trim()
                        ))))
                .then(ClientCommandsCompat.literal("add")
                    .then(ClientCommandsCompat.argument("job", StringArgumentType.greedyString())
                        .executes(context -> add(
                            context.getSource(),
                            StringArgumentType.getString(context, "job").trim(),
                            false
                        ))))
                .then(ClientCommandsCompat.literal("start")
                    .executes(context -> start(context.getSource(), null))
                    .then(ClientCommandsCompat.argument("job", StringArgumentType.greedyString())
                        .executes(context -> start(
                            context.getSource(),
                            StringArgumentType.getString(context, "job").trim()
                        ))))
                .then(ClientCommandsCompat.literal("resume")
                    .executes(context -> resume(context.getSource(), null))
                    .then(ClientCommandsCompat.argument("job", StringArgumentType.greedyString())
                        .executes(context -> resume(
                            context.getSource(),
                            StringArgumentType.getString(context, "job").trim()
                        ))))
                .then(ClientCommandsCompat.literal("pause")
                    .executes(context -> pause(context.getSource())))
                .then(ClientCommandsCompat.literal("status")
                    .executes(context -> status(context.getSource())))
                .then(ClientCommandsCompat.literal("list")
                    .executes(context -> list(context.getSource())))
                .then(ClientCommandsCompat.literal("cancel")
                    .executes(context -> cancel(context.getSource(), null))
                    .then(ClientCommandsCompat.argument("job", StringArgumentType.greedyString())
                        .executes(context -> cancel(
                            context.getSource(),
                            StringArgumentType.getString(context, "job").trim()
                        ))))
                .then(ClientCommandsCompat.literal("stop")
                    .executes(context -> stop(context.getSource())))
                .then(ClientCommandsCompat.literal("remove")
                    .then(ClientCommandsCompat.argument("job", StringArgumentType.greedyString())
                        .executes(context -> remove(
                            context.getSource(),
                            StringArgumentType.getString(context, "job").trim()
                        ))))
                .then(ClientCommandsCompat.literal("retry")
                    .then(ClientCommandsCompat.argument("job", StringArgumentType.greedyString())
                        .executes(context -> retry(
                            context.getSource(),
                            StringArgumentType.getString(context, "job").trim()
                        ))))
                .then(ClientCommandsCompat.literal("queue")
                    .then(ClientCommandsCompat.literal("add")
                        .then(ClientCommandsCompat.argument("job", StringArgumentType.greedyString())
                            .executes(context -> add(
                                context.getSource(),
                                StringArgumentType.getString(context, "job").trim(),
                                true
                            ))))
                    .then(ClientCommandsCompat.literal("list")
                        .executes(context -> {
                            noteLegacy(context.getSource(), "queue list", "list");
                            return list(context.getSource());
                        }))
                    .then(ClientCommandsCompat.literal("start")
                        .executes(context -> {
                            noteLegacy(context.getSource(), "queue start", "start");
                            return start(context.getSource(), null);
                        }))
                    .then(ClientCommandsCompat.literal("clear")
                        .executes(context -> clearLegacy(context.getSource())))
                )
                .then(ClientCommandsCompat.literal("ui")
                    .executes(context -> openConfigUi(context.getSource())))
                .then(ClientCommandsCompat.literal("config")
                    .executes(context -> showConfig(context.getSource()))
                    .then(ClientCommandsCompat.argument("key", StringArgumentType.word())
                        .then(ClientCommandsCompat.argument("value", StringArgumentType.word())
                            .executes(context -> setConfig(
                                context.getSource(),
                                StringArgumentType.getString(context, "key"),
                                StringArgumentType.getString(context, "value")
                            )))))
        );
    }

    private static int help(FabricClientCommandSource source, String topic) {
        List<String> lines = HelpText.topicLines(topic);
        if (lines == null) {
            source.sendError(Component.literal("AutoBook: 未知帮助主题 " + topic));
            source.sendFeedback(Component.literal("可用主题: " + HelpText.topicList()));
            return 0;
        }
        for (String line : lines) {
            source.sendFeedback(Component.literal(line));
        }
        return 1;
    }

    private static int plan(FabricClientCommandSource source, String jobName) {
        try {
            JobRunner.Prepared prepared = JobRunner.prepare(jobName);
            AutoBookConfig config = AutoBookConfig.get();
            JobRunner.Settings settings = prepared.settings();
            List<PlannedBook> books = prepared.books();
            if (books.isEmpty()) {
                source.sendError(Component.literal("AutoBook: 计划为空"));
                return 0;
            }
            int totalPages = books.stream().mapToInt(book -> book.pages().size()).sum();
            source.sendFeedback(Component.literal(
                "AutoBook 计划: " + books.size() + " 本, " + totalPages + " 页"
            ));
            source.sendFeedback(Component.literal(
                "每本上限: " + JobRunner.effectiveLimit(prepared.job(), settings) + " 页, 标点断书: "
                    + (settings.breakAtSentence() ? "开" : "关")
            ));
            boolean verify = settings.verifyContent() != null
                ? settings.verifyContent()
                : config.verifyContent;
            source.sendFeedback(Component.literal(
                "内容校验: " + (verify ? "开" : "关") + ", 自动恢复: " + (config.autoRecover ? "开" : "关")
            ));
            source.sendFeedback(Component.literal("空书需求: " + books.size() + " 本"));
            PlannedBook first = books.get(0);
            source.sendFeedback(Component.literal(
                "第一本: " + first.title() + " (" + first.pages().size() + " 页)"
            ));
            return books.size();
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int add(FabricClientCommandSource source, String jobName, boolean legacy) {
        if (legacy) {
            noteLegacy(source, "queue add", "add");
        }
        try {
            RunJob job = RunRunner.get().add(jobName);
            source.sendFeedback(Component.literal(
                "AutoBook: 已加入 " + job.name + "（" + job.totalBooks + " 本, "
                    + job.totalPages + " 页）；/autobook start 开始"
            ));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int start(FabricClientCommandSource source, String jobName) {
        try {
            RunRunner runner = RunRunner.get();
            if (jobName != null && !jobName.isBlank()) {
                RunState run = runner.state();
                boolean hasActiveRun = !RunState.RUN_COMPLETED.equals(run.status)
                    && !RunState.RUN_FAILED.equals(run.status)
                    && !RunState.RUN_CANCELLED.equals(run.status)
                    && !run.jobs.isEmpty();
                if (hasActiveRun) {
                    source.sendError(Component.literal(
                        "AutoBook: 已有运行，请先 /autobook stop，或使用 /autobook add " + jobName
                    ));
                    return 0;
                }
                runner.add(jobName);
            }
            runner.start();
            RunState run = runner.state();
            RunJob current = run.current();
            source.sendFeedback(Component.literal(
                "AutoBook: 运行已开始，共 " + run.jobs.size() + " 个任务"
                    + (current == null ? "" : "；当前 " + current.name)
            ));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int resume(FabricClientCommandSource source, String jobName) {
        try {
            RunRunner runner = RunRunner.get();
            RunJob current = runner.state().current();
            if (jobName != null && !jobName.isBlank() && current != null
                && !jobName.equals(current.name)) {
                source.sendError(Component.literal(
                    "AutoBook: 当前暂停的是 " + current.name + "，请使用相同任务名"
                ));
                return 0;
            }
            runner.resume();
            RunJob job = runner.state().current();
            source.sendFeedback(Component.literal(
                "AutoBook: 继续 " + (job == null ? "运行" : job.name)
                    + (job == null ? "" : "，第 " + (job.nextIndex + 1) + "/" + job.totalBooks + " 本")
            ));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int pause(FabricClientCommandSource source) {
        try {
            String message = RunRunner.get().pause();
            source.sendFeedback(Component.literal("AutoBook: " + message));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int status(FabricClientCommandSource source) {
        StringBuilder text = new StringBuilder("AutoBook: ").append(RunRunner.get().statusText());
        BookWriter.Progress progress = BookWriter.get().progress();
        if (!(progress.state() == BookWriter.State.IDLE || progress.state() == BookWriter.State.DONE)) {
            text.append("\n  ").append(BookWriter.get().status());
        }
        source.sendFeedback(Component.literal(text.toString()));
        return 1;
    }

    private static int list(FabricClientCommandSource source) {
        source.sendFeedback(Component.literal("AutoBook " + RunRunner.get().describe()));
        return 1;
    }

    private static int cancel(FabricClientCommandSource source, String jobName) {
        try {
            RunJob job = RunRunner.get().cancel(jobName);
            source.sendFeedback(Component.literal(
                "AutoBook: 已取消 " + job.name + "；/autobook list 查看剩余任务"
            ));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int stop(FabricClientCommandSource source) {
        try {
            RunRunner.get().stop();
            source.sendFeedback(Component.literal(
                "AutoBook: 运行已终止（CANCELLED），进度文件保留；可用 /autobook start <任务名> 重新开始"
            ));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int remove(FabricClientCommandSource source, String jobName) {
        try {
            RunJob job = RunRunner.get().remove(jobName);
            source.sendFeedback(Component.literal("AutoBook: 已移除 " + job.name));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int retry(FabricClientCommandSource source, String jobName) {
        try {
            RunJob job = RunRunner.get().retry(jobName);
            source.sendFeedback(Component.literal(
                "AutoBook: 已重新入队 " + job.name + "；/autobook start 继续"
            ));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static int clearLegacy(FabricClientCommandSource source) {
        noteLegacy(source, "queue clear", "stop + remove");
        try {
            RunRunner.get().clear();
            source.sendFeedback(Component.literal("AutoBook: 已清空运行与任务列表"));
            return 1;
        } catch (Exception error) {
            return fail(source, error);
        }
    }

    private static void noteLegacy(FabricClientCommandSource source, String legacy, String replacement) {
        source.sendFeedback(Component.literal(
            "AutoBook: /autobook " + legacy + " 已弃用，请改用 /autobook " + replacement
        ));
    }

    private static int showConfig(FabricClientCommandSource source) {
        source.sendFeedback(Component.literal("AutoBook 配置:\n" + AutoBookConfig.get().describe()));
        return 1;
    }

    private static int openConfigUi(FabricClientCommandSource source) {
        UiScreens.requestConfigScreen();
        source.sendFeedback(Component.literal("AutoBook: 正在打开配置界面"));
        return 1;
    }

    private static int setConfig(FabricClientCommandSource source, String key, String value) {
        AutoBookConfig config = AutoBookConfig.get();
        try {
            config.set(key, value);
            config.save();
            source.sendFeedback(Component.literal(
                "AutoBook: 已设置 " + key + "=" + value + "（下次 plan/start 生效；当前运行中的计划不变）"
            ));
            return 1;
        } catch (IllegalArgumentException | IOException error) {
            return fail(source, error);
        }
    }

    private static int fail(FabricClientCommandSource source, Exception error) {
        String text = error.getMessage();
        if (text == null || text.isBlank()) {
            text = error.getClass().getSimpleName();
        }
        source.sendError(Component.literal("AutoBook: " + text));
        source.sendFeedback(Component.literal("提示: /autobook help 查看命令说明"));
        return 0;
    }
}
