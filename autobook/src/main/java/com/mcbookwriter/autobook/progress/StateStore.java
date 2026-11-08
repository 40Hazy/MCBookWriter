package com.mcbookwriter.autobook.progress;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParseException;
import com.mcbookwriter.autobook.AutoBookPaths;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

public final class StateStore {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private final Path directory;

    public StateStore(Path directory) {
        this.directory = directory;
    }

    public static StateStore defaultStore() {
        Path directory = AutoBookPaths.stateDir();
        return new StateStore(directory);
    }

    public Path pathFor(String planHash) {
        return directory.resolve(planHash + ".json");
    }

    public RunState load(String planHash) throws IOException {
        Path path = pathFor(planHash);
        if (!Files.isRegularFile(path)) {
            return null;
        }
        try {
            RunState state = GSON.fromJson(Files.readString(path, StandardCharsets.UTF_8), RunState.class);
            if (state == null || !planHash.equals(state.planHash)) {
                return null;
            }
            return state;
        } catch (JsonParseException error) {
            throw new IOException("Invalid state file: " + path, error);
        }
    }

    public void save(RunState state) throws IOException {
        Files.createDirectories(directory);
        Path target = pathFor(state.planHash);
        Path temp = target.resolveSibling(target.getFileName() + ".tmp");
        Files.writeString(temp, GSON.toJson(state), StandardCharsets.UTF_8);
        try {
            Files.move(temp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException error) {
            Files.move(temp, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }
}
