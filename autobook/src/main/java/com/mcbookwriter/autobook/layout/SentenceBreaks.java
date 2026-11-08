package com.mcbookwriter.autobook.layout;

public final class SentenceBreaks {
    private static final String TERMINATORS = "。！？!?…．.";
    private static final String CLOSERS = "”’\"'」』】）》〉〕）]＇＂";

    private SentenceBreaks() {
    }

    public static boolean endsAtSentence(String text) {
        int index = lastNonWhitespace(text);
        while (index >= 0 && CLOSERS.indexOf(text.charAt(index)) >= 0) {
            index = previousNonWhitespace(text, index - 1);
        }
        return index >= 0 && TERMINATORS.indexOf(text.charAt(index)) >= 0;
    }

    public static boolean startsWithCloser(String text) {
        int index = firstNonWhitespace(text);
        return index >= 0 && CLOSERS.indexOf(text.charAt(index)) >= 0;
    }

    private static int firstNonWhitespace(String text) {
        for (int i = 0; i < text.length(); i++) {
            if (!Character.isWhitespace(text.charAt(i))) {
                return i;
            }
        }
        return -1;
    }

    private static int lastNonWhitespace(String text) {
        return previousNonWhitespace(text, text.length() - 1);
    }

    private static int previousNonWhitespace(String text, int from) {
        for (int i = Math.min(from, text.length() - 1); i >= 0; i--) {
            if (!Character.isWhitespace(text.charAt(i))) {
                return i;
            }
        }
        return -1;
    }
}
