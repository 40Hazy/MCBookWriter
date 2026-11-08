package com.mcbookwriter.autobook.verify;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;

public final class ContentVerifier {
    private ContentVerifier() {
    }

    public record Result(
        boolean ok,
        int expectedPages,
        int actualPages,
        int firstMismatchPage,
        String expectedPreview,
        String actualPreview,
        String expectedDigest,
        String actualDigest
    ) {
    }

    public static Result verify(List<String> expected, List<String> actual) {
        int expectedPages = expected.size();
        int actualPages = actual.size();
        int common = Math.min(expectedPages, actualPages);

        for (int index = 0; index < common; index++) {
            String want = normalize(expected.get(index));
            String got = normalize(actual.get(index));
            if (!want.equals(got)) {
                return new Result(
                    false,
                    expectedPages,
                    actualPages,
                    index + 1,
                    preview(want),
                    preview(got),
                    digest(expected),
                    digest(actual)
                );
            }
        }

        if (expectedPages != actualPages) {
            return new Result(
                false,
                expectedPages,
                actualPages,
                common + 1,
                "",
                "",
                digest(expected),
                digest(actual)
            );
        }

        String expectedDigest = digest(expected);
        return new Result(true, expectedPages, actualPages, 0, "", "", expectedDigest, digest(actual));
    }

    /**
     * 对规范化后的整书页面计算 SHA-256，用于整书内容摘要与日志追踪。
     */
    public static String digest(List<String> pages) {
        try {
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            for (String page : pages) {
                sha.update(normalize(page).getBytes(StandardCharsets.UTF_8));
                sha.update((byte) 0);
            }
            return toHex(sha.digest());
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException("SHA-256 is unavailable", error);
        }
    }

    private static String toHex(byte[] bytes) {
        StringBuilder hex = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            hex.append(Character.forDigit((value >> 4) & 0xF, 16));
            hex.append(Character.forDigit(value & 0xF, 16));
        }
        return hex.toString();
    }

    public static String normalize(String text) {
        StringBuilder stripped = new StringBuilder(text.length());
        for (int i = 0; i < text.length(); i++) {
            char value = text.charAt(i);
            if (value == '\u00a7') {
                i++;
                continue;
            }
            if (value != '\r') {
                stripped.append(value);
            }
        }

        String[] lines = stripped.toString().split("\n", -1);
        StringBuilder normalized = new StringBuilder();
        for (int i = 0; i < lines.length; i++) {
            if (i > 0) {
                normalized.append('\n');
            }
            normalized.append(lines[i].stripTrailing());
        }
        return normalized.toString().strip();
    }

    private static String preview(String text) {
        return text.length() <= 40 ? text : text.substring(0, 40) + "...";
    }
}
