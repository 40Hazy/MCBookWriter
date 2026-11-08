package com.mcbookwriter.autobook.progress;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class StateStoreTest {
    @TempDir
    Path tempDir;

    private RunState state(String hash) {
        RunState state = new RunState();
        state.jobName = "三体1";
        state.sourceHash = "source";
        state.planHash = hash;
        state.nextIndex = 7;
        state.completedBooks = 7;
        state.totalBooks = 36;
        state.totalPages = 1195;
        state.updatedAt = "2026-10-25T12:00:00+08:00";
        return state;
    }

    @Test
    void savesAndLoadsProgress() throws Exception {
        StateStore store = new StateStore(tempDir);
        store.save(state("abc123"));

        RunState loaded = store.load("abc123");
        assertNotNull(loaded);
        assertEquals(7, loaded.nextIndex);
        assertEquals(36, loaded.totalBooks);
        assertEquals("三体1", loaded.jobName);
    }

    @Test
    void returnsNullWhenStateIsMissing() throws Exception {
        StateStore store = new StateStore(tempDir);
        assertNull(store.load("missing"));
    }

    @Test
    void ignoresStateFromAnotherPlan() throws Exception {
        StateStore store = new StateStore(tempDir);
        store.save(state("other"));

        assertNull(store.load("abc123"));
    }

    @Test
    void persistsForceRewriteFlag() throws Exception {
        StateStore store = new StateStore(tempDir);
        RunState state = state("force");
        state.forceRewrite = true;
        store.save(state);

        assertTrue(store.load("force").forceRewrite);
    }

    @Test
    void persistsVerifiedBookCount() throws Exception {
        StateStore store = new StateStore(tempDir);
        RunState state = state("verified");
        state.verifiedBooks = 5;
        store.save(state);

        assertEquals(5, store.load("verified").verifiedBooks);
    }

    @Test
    void rejectsBrokenStateFile() throws Exception {
        StateStore store = new StateStore(tempDir);
        Path path = store.pathFor("broken");
        Files.createDirectories(path.getParent());
        Files.writeString(path, "{not json", StandardCharsets.UTF_8);

        assertThrows(java.io.IOException.class, () -> store.load("broken"));
    }
}
