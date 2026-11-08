package com.mcbookwriter.autobook.gui;

import com.mcbookwriter.autobook.compat.ScreenCompat;
import com.mcbookwriter.autobook.help.HelpText;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphicsExtractor;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 游戏内说明页：分页展示 HelpText，可从配置界面进入并返回。
 */
public final class AutoBookHelpScreen extends Screen {
    private static final int LINE_HEIGHT = 12;

    private final Screen parent;
    private final List<String> lines = new ArrayList<>();
    private int page;
    private int linesPerPage = 1;
    private int totalPages = 1;
    private Button prevButton;
    private Button nextButton;

    public AutoBookHelpScreen(Screen parent) {
        super(Component.literal("AutoBook 帮助"));
        this.parent = parent;
    }

    @Override
    protected void init() {
        lines.clear();
        int maxWidth = Math.max(120, width - 80);
        for (String line : HelpText.lines()) {
            if (line.isBlank()) {
                lines.add("");
                continue;
            }
            lines.addAll(wrapLine(line, maxWidth));
        }
        linesPerPage = Math.max(1, (height - 100) / LINE_HEIGHT);
        totalPages = Math.max(1, (lines.size() + linesPerPage - 1) / linesPerPage);
        if (page >= totalPages) {
            page = totalPages - 1;
        }

        int buttonsY = height - 32;
        prevButton = Button.builder(Component.literal("上一页"), pressed -> turn(-1))
            .bounds(width / 2 - 160, buttonsY, 100, 20)
            .build();
        nextButton = Button.builder(Component.literal("下一页"), pressed -> turn(1))
            .bounds(width / 2 - 50, buttonsY, 100, 20)
            .build();
        addRenderableWidget(prevButton);
        addRenderableWidget(nextButton);
        addRenderableWidget(Button.builder(Component.literal("返回"), pressed -> onClose())
            .bounds(width / 2 + 60, buttonsY, 100, 20)
            .build());
        updateButtons();
    }

    private List<String> wrapLine(String text, int maxWidth) {
        List<String> result = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        for (int index = 0; index < text.length(); index++) {
            char value = text.charAt(index);
            if (current.length() > 0 && font.width(current + String.valueOf(value)) > maxWidth) {
                result.add(current.toString());
                current.setLength(0);
            }
            current.append(value);
        }
        if (current.length() > 0) {
            result.add(current.toString());
        }
        return result;
    }

    private void turn(int delta) {
        page = Math.max(0, Math.min(totalPages - 1, page + delta));
        updateButtons();
    }

    private void updateButtons() {
        if (prevButton != null) {
            prevButton.active = page > 0;
        }
        if (nextButton != null) {
            nextButton.active = page < totalPages - 1;
        }
    }

    @Override
    public void extractRenderState(GuiGraphicsExtractor graphics, int mouseX, int mouseY, float partialTick) {
        super.extractRenderState(graphics, mouseX, mouseY, partialTick);
        graphics.centeredText(font, title, width / 2, 20, 0xFFFFFFFF);

        int first = page * linesPerPage;
        for (int i = 0; i < linesPerPage; i++) {
            int index = first + i;
            if (index >= lines.size()) {
                break;
            }
            graphics.text(font, lines.get(index), 40, 40 + i * LINE_HEIGHT, 0xFFE0E0E0);
        }
        graphics.centeredText(
            font,
            "第 " + (page + 1) + "/" + totalPages + " 页",
            width / 2,
            height - 48,
            0xFFA0A0A0
        );
    }

    @Override
    public void onClose() {
        ScreenCompat.set(Minecraft.getInstance(), parent);
    }
}
