package com.mcbookwriter.autobook.layout;

import net.minecraft.client.gui.Font;

public final class MinecraftWidthProvider implements WidthProvider {
    private final Font font;

    public MinecraftWidthProvider(Font font) {
        this.font = font;
    }

    @Override
    public int width(int codepoint) {
        return font.width(new String(Character.toChars(codepoint)));
    }
}
