package com.mcbookwriter.autobook.progress;

import com.mcbookwriter.autobook.layout.PlannedBook;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

public final class PlanDigest {
    private PlanDigest() {
    }

    public static String hash(String jobName, List<PlannedBook> books) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException("SHA-256 is unavailable", error);
        }

        update(digest, jobName);
        for (PlannedBook book : books) {
            update(digest, book.title());
            update(digest, Integer.toString(book.pages().size()));
            for (String page : book.pages()) {
                update(digest, page);
            }
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        digest.update((byte) (bytes.length >>> 24));
        digest.update((byte) (bytes.length >>> 16));
        digest.update((byte) (bytes.length >>> 8));
        digest.update((byte) bytes.length);
        digest.update(bytes);
    }
}
