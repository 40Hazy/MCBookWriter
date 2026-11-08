package com.mcbookwriter.autobook.run;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RunStateTest {
    @Test
    void appendsJobsAsPendingInOrder() {
        RunState state = new RunState();

        state.append("三体1");
        state.append("西游记");

        assertEquals(2, state.jobs.size());
        assertEquals("三体1", state.current().name);
        assertEquals(RunState.JOB_PENDING, state.current().status);
    }

    @Test
    void rejectsDuplicateActiveJobs() {
        RunState state = new RunState();
        state.append("三体1");

        assertThrows(IllegalArgumentException.class, () -> state.append("三体1"));
    }

    @Test
    void allowsReaddingFinishedJob() {
        RunState state = new RunState();
        RunJob job = state.append("三体1");
        job.status = RunState.JOB_COMPLETED;

        state.append("三体1");

        assertEquals(2, state.jobs.size());
    }

    @Test
    void normalizeSkipsTerminalJobs() {
        RunState state = new RunState();
        RunJob first = state.append("一");
        state.append("二");
        first.status = RunState.JOB_COMPLETED;

        state.normalize();

        assertEquals(1, state.currentIndex);
        assertEquals("二", state.current().name);
    }

    @Test
    void removeOnlyAcceptsQueuedJobs() {
        RunState state = new RunState();
        RunJob first = state.append("一");
        state.append("二");

        RunJob removed = state.remove("一");
        assertEquals("一", removed.name);
        assertEquals(1, state.jobs.size());
        assertEquals("二", state.current().name);

        first.status = RunState.JOB_RUNNING;
        state.jobs.add(first);
        assertThrows(IllegalArgumentException.class, () -> state.remove("一"));
    }

    @Test
    void nextQueuedIndexSkipsTerminalJobs() {
        RunState state = new RunState();
        RunJob first = state.append("一");
        RunJob second = state.append("二");
        first.status = RunState.JOB_COMPLETED;
        second.status = RunState.JOB_CANCELLED;
        state.normalize();

        assertEquals(-1, state.nextQueuedIndex(0));
        assertFalse(state.hasQueued());
        assertTrue(state.allTerminal());
        assertNull(state.current());
    }

    @Test
    void findHelpersPreferActiveAndEndedJobs() {
        RunState state = new RunState();
        RunJob completed = state.append("一");
        completed.status = RunState.JOB_COMPLETED;
        RunJob failed = state.append("二");
        failed.status = RunState.JOB_FAILED;

        assertNull(state.findNonTerminal("一"));

        RunJob queued = state.append("一");
        assertEquals(queued, state.findNonTerminal("一"));
        assertEquals(failed, state.findEnded("二"));
        assertEquals("二", state.remove("二").name);
    }

    @Test
    void missingFieldsAreNormalised() {
        RunState state = new RunState();
        RunJob job = new RunJob();
        job.name = "一";
        job.status = null;
        job.error = null;
        job.planHash = null;
        state.jobs.add(job);

        state.ensureDefaults();

        assertEquals(RunState.JOB_PENDING, job.status);
        assertTrue(job.error.isEmpty());
        assertTrue(job.planHash.isEmpty());
    }
}
