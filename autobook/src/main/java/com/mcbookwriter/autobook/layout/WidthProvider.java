package com.mcbookwriter.autobook.layout;

@FunctionalInterface
public interface WidthProvider {
    int width(int codepoint);
}
