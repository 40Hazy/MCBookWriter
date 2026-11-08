package com.mcbookwriter.autobook.run;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class StatusStoreTest {
    @TempDir
    Path tempDir;

    @Test
    void writesSnapshotAtomically() throws Exception {
        Path path = tempDir.resolve("status.json");
        StatusStore store = new StatusStore(path);
        RunState run = runningRun();

        store.writeNow(run);

        assertTrue(Files.exists(path));
        assertFalse(Files.exists(tempDir.resolve("status.json.tmp")));
        JsonObject root = JsonParser.parseString(
            Files.readString(path, StandardCharsets.UTF_8)
        ).getAsJsonObject();
        assertEquals(1, root.get("schema").getAsInt());
        assertEquals("running", root.get("runStatus").getAsString());
        assertEquals("三体1", root.get("currentJob").getAsString());
        assertEquals(4, root.get("nextIndex").getAsInt());
        assertEquals(4, root.get("completedBooks").getAsInt());
        assertEquals(10, root.get("totalBooks").getAsInt());
        assertEquals(3, root.get("verifiedBooks").getAsInt());
        assertFalse(root.get("updatedAt").getAsString().isBlank());
        assertFalse(root.get("autoBookVersion").getAsString().isBlank());
    }

    @Test
    void tickThrottlesChangesWithinOneSecond() throws Exception {
        Path path = tempDir.resolve("status.json");
        StatusStore store = new StatusStore(path);
        RunState run = runningRun();
        store.writeNow(run);
        String first = Files.readString(path, StandardCharsets.UTF_8);

        store.tick(run);
        assertEquals(first, Files.readString(path, StandardCharsets.UTF_8));

        run.status = RunState.RUN_PAUSED;
        run.current().nextIndex = 6;
        store.tick(run);
        assertEquals(first, Files.readString(path, StandardCharsets.UTF_8));

        store.writeNow(run);
        JsonObject root = JsonParser.parseString(
            Files.readString(path, StandardCharsets.UTF_8)
        ).getAsJsonObject();
        assertEquals("paused", root.get("runStatus").getAsString());
        assertEquals(6, root.get("nextIndex").getAsInt());
    }

    @Test
    void failuresDoNotEscape() throws Exception {
        Path blocker = tempDir.resolve("blocked");
        Files.writeString(blocker, "not a directory", StandardCharsets.UTF_8);
        StatusStore store = new StatusStore(blocker.resolve("status.json"));

        assertDoesNotThrow(() -> store.writeNow(runningRun()));
        assertDoesNotThrow(() -> store.tick(runningRun()));
    }

    private static RunState runningRun() {
        RunState run = new RunState();
        run.status = RunState.RUN_RUNNING;
        RunJob job = run.append("三体1");
        job.nextIndex = 4;
        job.completedBooks = 4;
        job.totalBooks = 10;
        job.verifiedBooks = 3;
        return run;
    }
}
