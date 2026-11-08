package com.mcbookwriter.autobook.gui;

import com.mcbookwriter.autobook.compat.ScreenCompat;
import com.mcbookwriter.autobook.config.AutoBookConfig;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

public final class AutoBookConfigScreen extends Screen {
    private record BoolField(String key, String label, Function<AutoBookConfig, Boolean> getter) {
    }

    private record IntField(String key, String label, Function<AutoBookConfig, Integer> getter) {
    }

    private static final int ROW_HEIGHT = 22;
    private static final int START_Y = 38;
    private static final int WIDE_BUTTON = 168;

    private static final List<BoolField> BOOL_FIELDS = List.of(
        new BoolField("keepWrittenBooks", "保留成书", config -> config.keepWrittenBooks),
        new BoolField("skipExistingBooks", "跳过已印书", config -> config.skipExistingBooks),
        new BoolField("breakAtSentence", "标点断书", config -> config.breakAtSentence),
        new BoolField("verifyContent", "内容校验", config -> config.verifyContent),
        new BoolField("autoRecover", "自动恢复", config -> config.autoRecover),
        new BoolField("queueStopOnFailure", "队列失败即停", config -> config.queueStopOnFailure)
    );

    private static final List<IntField> INT_FIELDS = List.of(
        new IntField("pageLimit", "每本页数 (0=job)", config -> config.pageLimit),
        new IntField("recoveryWaitTicks", "恢复等待 tick", config -> config.recoveryWaitTicks),
        new IntField("settleTicks", "开始缓冲 tick", config -> config.settleTicks),
        new IntField("inventoryWaitTicks", "空书等待 tick", config -> config.inventoryWaitTicks),
        new IntField("confirmWaitTicks", "确认等待 tick", config -> config.confirmWaitTicks),
        new IntField("retryDelayTicks", "重试等待 tick", config -> config.retryDelayTicks),
        new IntField("maxInventoryRetries", "空书重试次数", config -> config.maxInventoryRetries)
    );

    private final Map<String, Boolean> boolValues = new LinkedHashMap<>();
    private final Map<String, EditBox> intBoxes = new LinkedHashMap<>();
    private String error = "";

    public AutoBookConfigScreen() {
        super(Component.literal("AutoBook 配置"));
    }

    @Override
    protected void init() {
        AutoBookConfig config = AutoBookConfig.get();
        boolValues.clear();
        intBoxes.clear();

        int center = width / 2;
        int leftX = center - 172;
        int rightX = center + 4;
        int startY = START_Y;

        for (int i = 0; i < BOOL_FIELDS.size(); i++) {
            BoolField field = BOOL_FIELDS.get(i);
            boolean value = field.getter().apply(config);
            boolValues.put(field.key(), value);
            Button button = Button.builder(
                boolLabel(field, value),
                pressed -> {
                    boolean next = !boolValues.getOrDefault(field.key(), false);
                    boolValues.put(field.key(), next);
                    pressed.setMessage(boolLabel(field, next));
                }
            ).bounds(leftX, startY + i * ROW_HEIGHT, WIDE_BUTTON, 18).build();
            addRenderableWidget(button);
        }

        for (int i = 0; i < INT_FIELDS.size(); i++) {
            IntField field = INT_FIELDS.get(i);
            int y = startY + i * ROW_HEIGHT;
            EditBox box = new EditBox(font, rightX + 104, y, 64, 18, Component.literal(field.label()));
            box.setValue(Integer.toString(field.getter().apply(config)));
            box.setMaxLength(6);
            intBoxes.put(field.key(), box);
            addRenderableWidget(box);
        }

        int buttonsY = height - 32;
        addRenderableWidget(Button.builder(
            Component.literal("保存并关闭"),
            pressed -> save()
        ).bounds(center - 160, buttonsY, 100, 20).build());
        addRenderableWidget(Button.builder(
            Component.literal("说明"),
            pressed -> ScreenCompat.set(Minecraft.getInstance(), new AutoBookHelpScreen(this))
        ).bounds(center - 50, buttonsY, 100, 20).build());
        addRenderableWidget(Button.builder(
            Component.literal("取消"),
            pressed -> onClose()
        ).bounds(center + 60, buttonsY, 100, 20).build());
    }

    private static Component boolLabel(BoolField field, boolean value) {
        return Component.literal(field.label() + ": " + (value ? "开" : "关"));
    }

    private void save() {
        AutoBookConfig config = AutoBookConfig.get();
        error = "";
        try {
            for (BoolField field : BOOL_FIELDS) {
                config.set(field.key(), boolValues.getOrDefault(field.key(), false) ? "true" : "false");
            }
            for (IntField field : INT_FIELDS) {
                EditBox box = intBoxes.get(field.key());
                config.set(field.key(), box == null ? "" : box.getValue().trim());
            }
            config.save();
            onClose();
        } catch (IllegalArgumentException exception) {
            error = exception.getMessage();
        } catch (IOException exception) {
            error = "保存失败: " + exception.getMessage();
        }
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        super.render(graphics, mouseX, mouseY, partialTick);
        graphics.drawCenteredString(font, title, width / 2, 20, 0xFFFFFFFF);

        int center = width / 2;
        int rightX = center + 4;
        int startY = START_Y;
        for (int i = 0; i < INT_FIELDS.size(); i++) {
            IntField field = INT_FIELDS.get(i);
            int y = startY + i * ROW_HEIGHT;
            graphics.drawString(font, field.label(), rightX, y + 5, 0xFFA0A0A0);
        }

        if (!error.isEmpty()) {
            graphics.drawCenteredString(font, error, width / 2, height - 52, 0xFFFF5555);
        }
    }

    @Override
    public void onClose() {
        ScreenCompat.set(Minecraft.getInstance(), null);
    }
}
