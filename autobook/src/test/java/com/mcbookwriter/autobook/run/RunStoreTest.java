package com.mcbookwriter.autobook.run;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RunStoreTest {
    @TempDir
    Path tempDir;

    @Test
    void savesAndLoadsRun() throws Exception {
        RunStore store = store();
        RunState run = new RunState();
        run.status = RunState.RUN_RUNNING;
        RunJob first = run.append("三体1");
        first.status = RunState.JOB_COMPLETED;
        RunJob second = run.append("西游记");
        second.status = RunState.JOB_RUNNING;
        second.nextIndex = 4;
        second.totalBooks = 10;
        second.completedBooks = 4;
        second.verifiedBooks = 3;
        run.currentIndex = 1;

        store.save(run);
        RunState loaded = store.load();

        assertEquals(RunState.RUN_RUNNING, loaded.status);
        assertEquals(1, loaded.currentIndex);
        assertEquals(2, loaded.jobs.size());
        assertEquals("西游记", loaded.current().name);
        assertEquals(4, loaded.current().nextIndex);
        assertEquals(3, loaded.current().verifiedBooks);
    }

    @Test
    void returnsCreatedRunWhenFileIsMissing() throws Exception {
        RunState loaded = store().load();

        assertEquals(RunState.RUN_CREATED, loaded.status);
        assertEquals(0, loaded.jobs.size());
    }

    @Test
    void rejectsBrokenRunFile() throws Exception {
        Path path = tempDir.resolve("run.json");
        Files.writeString(path, "{not json", StandardCharsets.UTF_8);

        RunStore store = new RunStore(path, tempDir.resolve("queue.json"));
        assertThrows(java.io.IOException.class, store::load);
    }

    @Test
    void migratesLegacyQueueFile() throws Exception {
        Path legacy = tempDir.resolve("queue.json");
        Files.writeString(legacy, """
            {
              "version": 1,
              "active": true,
              "currentIndex": 1,
              "jobs": [
                {"name": "三体1", "status": "completed", "completedBooks": 13, "totalBooks": 13},
                {"name": "三体2", "status": "running", "nextIndex": 3, "completedBooks": 3, "totalBooks": 20},
                {"name": "三体3", "status": "pending", "totalBooks": 12}
              ]
            }
            """, StandardCharsets.UTF_8);

        RunState loaded = store().load();

        assertEquals(RunState.RUN_PAUSED, loaded.status);
        assertEquals(3, loaded.jobs.size());
        assertEquals(RunState.JOB_COMPLETED, loaded.jobs.get(0).status);
        assertEquals(RunState.JOB_PAUSED, loaded.jobs.get(1).status);
        assertEquals(RunState.JOB_QUEUED, loaded.jobs.get(2).status);
        assertEquals(3, loaded.jobs.get(1).nextIndex);
        assertTrue(Files.exists(tempDir.resolve("queue.json.bak")));
    }

    @Test
    void legacyInactiveQueueBecomesCompleted() throws Exception {
        Path legacy = tempDir.resolve("queue.json");
        Files.writeString(legacy, """
            {"version":1,"active":false,"currentIndex":0,"jobs":[
              {"name":"三体1","status":"completed","completedBooks":13,"totalBooks":13}
            ]}
            """, StandardCharsets.UTF_8);

        RunState loaded = store().load();

        assertEquals(RunState.RUN_COMPLETED, loaded.status);
        assertEquals(1, loaded.jobs.size());
        assertFalse(Files.exists(legacy));
        assertTrue(Files.exists(tempDir.resolve("queue.json.bak")));
        assertTrue(Files.exists(tempDir.resolve("run.json")));
    }

    private RunStore store() {
        return new RunStore(tempDir.resolve("run.json"), tempDir.resolve("queue.json"));
    }
}
