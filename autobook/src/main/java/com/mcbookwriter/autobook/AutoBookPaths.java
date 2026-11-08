package com.mcbookwriter.autobook;

import net.fabricmc.loader.api.FabricLoader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.stream.Stream;

/**
 * AutoBook 的运行目录统一放在游戏目录下的 autobook/。
 *
 * <p>老版本使用 config/autobook/；首次启动时会把旧目录中不存在的文件迁移过来，
 * 不会覆盖新目录已有的文件。</p>
 */
public final class AutoBookPaths {
    private static final Logger LOG = LoggerFactory.getLogger("autobook");

    private AutoBookPaths() {
    }

    public static Path baseDir() {
        return FabricLoader.getInstance().getGameDir().resolve("autobook");
    }

    public static Path legacyDir() {
        return FabricLoader.getInstance().getConfigDir().resolve("autobook");
    }

    public static Path configFile() {
        return baseDir().resolve("config.json");
    }

    public static Path jobsDir() {
        return baseDir().resolve("jobs");
    }

    public static Path stateDir() {
        return baseDir().resolve("state");
    }

    public static Path runFile() {
        return baseDir().resolve("run.json");
    }

    /**
     * 0.10.0 之前的队列文件，仅用于首次启动迁移。
     */
    public static Path legacyQueueFile() {
        return baseDir().resolve("queue.json");
    }

    public static void ensureInitialized() {
        try {
            migrateLegacyFiles();
            Files.createDirectories(jobsDir());
            Files.createDirectories(stateDir());
        } catch (IOException error) {
            LOG.warn("AutoBook: failed to create data directory: {}", error.getMessage());
        }
    }

    private static void migrateLegacyFiles() throws IOException {
        Path legacy = legacyDir();
        if (!Files.isDirectory(legacy)) {
            return;
        }
        try (Stream<Path> children = Files.list(legacy)) {
            for (Path child : children.toList()) {
                Path target = baseDir().resolve(child.getFileName().toString());
                if (Files.exists(target)) {
                    continue;
                }
                copyRecursively(child, target);
                LOG.info("AutoBook: migrated {} to {}", child, target);
            }
        }
    }

    private static void copyRecursively(Path source, Path target) throws IOException {
        try (Stream<Path> stream = Files.walk(source)) {
            for (Path path : stream.toList()) {
                Path destination = target.resolve(source.relativize(path));
                if (Files.isDirectory(path)) {
                    Files.createDirectories(destination);
                } else {
                    Path parent = destination.getParent();
                    if (parent != null) {
                        Files.createDirectories(parent);
                    }
                    Files.copy(path, destination, StandardCopyOption.REPLACE_EXISTING);
                }
            }
        }
    }
}
