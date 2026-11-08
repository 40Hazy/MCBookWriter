package com.mcbookwriter.autobook.layout;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PageLayoutTest {
    private static final WidthProvider ONE_PIXEL = codepoint -> 1;

    @Test
    void breaksPagesEveryConfiguredLineCount() {
        List<String> pages = PageLayout.paginate("a\nb\nc", ONE_PIXEL, 10, 2, 1023);
        assertEquals(2, pages.size());
        assertEquals("a\nb", pages.get(0));
        assertEquals("c", pages.get(1));
    }

    @Test
    void wrapsWhenLineWidthIsExceeded() {
        List<String> pages = PageLayout.paginate("aaa", ONE_PIXEL, 2, 14, 1023);
        assertEquals(1, pages.size());
        assertEquals("aa\na", pages.get(0));
    }

    @Test
    void enforcesMaximumCharactersPerPage() {
        List<String> pages = PageLayout.paginate("abcdef", ONE_PIXEL, 100, 14, 3);
        assertEquals(2, pages.size());
        assertEquals("abc", pages.get(0));
        assertEquals("def", pages.get(1));
    }

    @Test
    void keepsSectionFormattingCodesInPages() {
        WidthProvider widths = codepoint -> codepoint == 'a' ? 6 : codepoint == 'b' ? 6 : 1;
        List<String> pages = PageLayout.paginate("\u00a7xab", widths, 10, 14, 1023);
        assertEquals(1, pages.size());
        assertTrue(pages.get(0).startsWith("\u00a7x"));
    }
}
