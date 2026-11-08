package com.mcbookwriter.autobook.layout;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SentenceBreaksTest {
    @Test
    void detectsSentenceEnd() {
        assertTrue(SentenceBreaks.endsAtSentence("他说完。"));
        assertTrue(SentenceBreaks.endsAtSentence("真的吗？\n"));
        assertTrue(SentenceBreaks.endsAtSentence("等等……"));
        assertTrue(SentenceBreaks.endsAtSentence("Stop."));
    }

    @Test
    void detectsSentenceEndBeforeClosingQuote() {
        assertTrue(SentenceBreaks.endsAtSentence("“走吧。”"));
        assertTrue(SentenceBreaks.endsAtSentence("「到了。」"));
    }

    @Test
    void rejectsTruncatedSentence() {
        assertFalse(SentenceBreaks.endsAtSentence("他说这"));
        assertFalse(SentenceBreaks.endsAtSentence("没有标点，"));
        assertFalse(SentenceBreaks.endsAtSentence(""));
    }

    @Test
    void detectsPageStartingWithClosingQuote() {
        assertTrue(SentenceBreaks.startsWithCloser("”。下一句"));
        assertFalse(SentenceBreaks.startsWithCloser("下一句。"));
    }
}
