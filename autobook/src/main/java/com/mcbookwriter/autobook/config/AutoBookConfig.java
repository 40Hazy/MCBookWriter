package com.mcbookwriter.autobook.config;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParseException;
import com.mcbookwriter.autobook.AutoBookPaths;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

public final class AutoBookConfig {
    private static final Logger LOG = LoggerFactory.getLogger("autobook");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    public boolean keepWrittenBooks = true;
    public boolean skipExistingBooks = true;
    public int pageLimit = 0;
    public boolean breakAtSentence = true;
    public boolean verifyContent = true;
    public boolean autoRecover = true;
    public int recoveryWaitTicks = 200;
    public int settleTicks = 15;
    public int inventoryWaitTicks = 80;
    public int confirmWaitTicks = 100;
    public int retryDelayTicks = 120;
    public int maxInventoryRetries = 3;
    public boolean queueStopOnFailure = false;

    public static AutoBookConfig get() {
        return load();
    }

    public static Path configPath() {
        return AutoBookPaths.configFile();
    }

    public String describe() {
        return String.join(
            "\n",
            "keepWrittenBooks = " + keepWrittenBooks,
            "skipExistingBooks = " + skipExistingBooks,
            "pageLimit = " + pageLimit,
            "breakAtSentence = " + breakAtSentence,
            "verifyContent = " + verifyContent,
            "autoRecover = " + autoRecover,
            "recoveryWaitTicks = " + recoveryWaitTicks,
            "settleTicks = " + settleTicks,
            "inventoryWaitTicks = " + inventoryWaitTicks,
            "confirmWaitTicks = " + confirmWaitTicks,
            "retryDelayTicks = " + retryDelayTicks,
            "maxInventoryRetries = " + maxInventoryRetries,
            "queueStopOnFailure = " + queueStopOnFailure
        );
    }

    public void set(String key, String value) {
        String normalizedKey = key.trim();
        String normalizedValue = value.trim();
        switch (normalizedKey) {
            case "keepWrittenBooks" -> keepWrittenBooks = parseBoolean(normalizedKey, normalizedValue);
            case "skipExistingBooks" -> skipExistingBooks = parseBoolean(normalizedKey, normalizedValue);
            case "pageLimit" -> pageLimit = parseRange(normalizedKey, normalizedValue, 0, 100);
            case "breakAtSentence" -> breakAtSentence = parseBoolean(normalizedKey, normalizedValue);
            case "verifyContent" -> verifyContent = parseBoolean(normalizedKey, normalizedValue);
            case "autoRecover" -> autoRecover = parseBoolean(normalizedKey, normalizedValue);
            case "recoveryWaitTicks" -> recoveryWaitTicks = parseRange(normalizedKey, normalizedValue, 20, 1200);
            case "settleTicks" -> settleTicks = parseRange(normalizedKey, normalizedValue, 1, 400);
            case "inventoryWaitTicks" -> inventoryWaitTicks = parseRange(normalizedKey, normalizedValue, 20, 600);
            case "confirmWaitTicks" -> confirmWaitTicks = parseRange(normalizedKey, normalizedValue, 20, 600);
            case "retryDelayTicks" -> retryDelayTicks = parseRange(normalizedKey, normalizedValue, 20, 1200);
            case "maxInventoryRetries" -> maxInventoryRetries = parseRange(normalizedKey, normalizedValue, 1, 10);
            case "queueStopOnFailure" -> queueStopOnFailure = parseBoolean(normalizedKey, normalizedValue);
            default -> throw new IllegalArgumentException("未知配置项: " + normalizedKey);
        }
    }

    public void save() throws IOException {
        Path path = configPath();
        Files.createDirectories(path.getParent());
        Files.writeString(path, GSON.toJson(this), StandardCharsets.UTF_8);
    }

    private static AutoBookConfig load() {
        Path path = configPath();
        if (!Files.isRegularFile(path)) {
            AutoBookConfig config = new AutoBookConfig();
            config.write(path);
            return config;
        }
        try {
            AutoBookConfig config = GSON.fromJson(Files.readString(path, StandardCharsets.UTF_8), AutoBookConfig.class);
            return config == null ? new AutoBookConfig() : config;
        } catch (IOException | JsonParseException error) {
            LOG.warn("AutoBook: failed to read config.json, using defaults: {}", error.getMessage());
            return new AutoBookConfig();
        }
    }

    private void write(Path path) {
        try {
            Files.createDirectories(path.getParent());
            Files.writeString(path, GSON.toJson(this), StandardCharsets.UTF_8);
        } catch (IOException error) {
            LOG.warn("AutoBook: failed to write default config.json: {}", error.getMessage());
        }
    }

    private static boolean parseBoolean(String key, String value) {
        return switch (value.toLowerCase()) {
            case "true", "on", "yes", "1" -> true;
            case "false", "off", "no", "0" -> false;
            default -> throw new IllegalArgumentException(key + " 需要 true 或 false，收到: " + value);
        };
    }

    private static int parseRange(String key, String value, int min, int max) {
        int parsed;
        try {
            parsed = Integer.parseInt(value);
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException(key + " 需要整数，收到: " + value);
        }
        if (parsed < min || parsed > max) {
            throw new IllegalArgumentException(key + " 必须在 " + min + "–" + max + " 之间，收到: " + parsed);
        }
        return parsed;
    }
}
