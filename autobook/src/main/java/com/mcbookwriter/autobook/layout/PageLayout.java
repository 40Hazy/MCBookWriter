package com.mcbookwriter.autobook.layout;

import java.util.ArrayList;
import java.util.List;

public final class PageLayout {
    public static final int DEFAULT_MAX_WIDTH = 114;
    public static final int DEFAULT_LINES_PER_PAGE = 14;
    public static final int DEFAULT_MAX_CHARS_PER_PAGE = 1023;

    private static final int SECTION_SIGN = '\u00a7';

    private PageLayout() {
    }

    public static List<String> paginate(String text, WidthProvider widthProvider) {
        return paginate(text, widthProvider, DEFAULT_MAX_WIDTH, DEFAULT_LINES_PER_PAGE, DEFAULT_MAX_CHARS_PER_PAGE);
    }

    public static List<String> paginate(
        String text,
        WidthProvider widthProvider,
        int maxWidth,
        int linesPerPage,
        int maxCharsPerPage
    ) {
        if (maxWidth <= 0 || linesPerPage <= 0 || maxCharsPerPage <= 0) {
            throw new IllegalArgumentException("Layout limits must be positive");
        }

        List<String> pages = new ArrayList<>();
        PageBuilder builder = new PageBuilder(pages, maxWidth, linesPerPage, maxCharsPerPage);
        boolean skipWidth = false;

        for (int offset = 0; offset < text.length(); ) {
            int codepoint = text.codePointAt(offset);
            offset += Character.charCount(codepoint);

            if (codepoint == '\r') {
                continue;
            }
            if (codepoint == '\n') {
                builder.newline();
                continue;
            }
            if (codepoint == SECTION_SIGN) {
                builder.appendRaw(codepoint);
                skipWidth = true;
                continue;
            }
            if (skipWidth) {
                builder.appendRaw(codepoint);
                skipWidth = false;
                continue;
            }
            if (codepoint == ' ' && builder.lineWidth() == 0) {
                continue;
            }

            builder.append(codepoint, Math.max(0, widthProvider.width(codepoint)));
        }

        builder.finish();
        return pages;
    }

    private static final class PageBuilder {
        private final List<String> pages;
        private final int maxWidth;
        private final int linesPerPage;
        private final int maxCharsPerPage;
        private final StringBuilder page = new StringBuilder();
        private int lineWidth;
        private int lineCount;

        private PageBuilder(List<String> pages, int maxWidth, int linesPerPage, int maxCharsPerPage) {
            this.pages = pages;
            this.maxWidth = maxWidth;
            this.linesPerPage = linesPerPage;
            this.maxCharsPerPage = maxCharsPerPage;
        }

        private int lineWidth() {
            return lineWidth;
        }

        private void append(int codepoint, int width) {
            if (lineWidth > 0 && lineWidth + width > maxWidth) {
                newline();
            }
            if (page.length() >= maxCharsPerPage) {
                finishPage();
            }
            page.appendCodePoint(codepoint);
            lineWidth += width;
        }

        private void appendRaw(int codepoint) {
            if (page.length() >= maxCharsPerPage) {
                finishPage();
            }
            page.appendCodePoint(codepoint);
        }

        private void newline() {
            page.append('\n');
            lineWidth = 0;
            lineCount++;
            if (lineCount >= linesPerPage) {
                finishPage();
            }
        }

        private void finishPage() {
            String value = page.toString();
            while (value.startsWith("\n")) {
                value = value.substring(1);
            }
            while (value.endsWith("\n")) {
                value = value.substring(0, value.length() - 1);
            }
            if (!value.isEmpty()) {
                pages.add(value);
            }
            page.setLength(0);
            lineWidth = 0;
            lineCount = 0;
        }

        private void finish() {
            finishPage();
        }
    }
}
