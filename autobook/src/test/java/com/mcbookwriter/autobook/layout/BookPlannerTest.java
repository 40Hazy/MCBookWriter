package com.mcbookwriter.autobook.layout;

import com.mcbookwriter.autobook.job.JobManifest;
import com.mcbookwriter.autobook.job.JobSegment;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class BookPlannerTest {
    private static final WidthProvider ONE_PIXEL = codepoint -> 1;

    private JobManifest job(int pageLimit, String text) {
        JobManifest job = new JobManifest();
        job.version = 1;
        job.titleBase = "T";
        job.pageLimit = pageLimit;
        JobSegment segment = new JobSegment();
        segment.index = 1;
        segment.chapter = "1. test";
        segment.text = text;
        job.segments = List.of(segment);
        return job;
    }

    @Test
    void groupsPagesIntoBooksUsingPageLimit() {
        String text = String.join("\n", Collections.nCopies(30, "x"));
        List<PlannedBook> books = BookPlanner.plan(job(1, text), ONE_PIXEL);
        assertEquals(3, books.size());
        assertEquals("T-01", books.get(0).title());
        assertEquals("T-03", books.get(2).title());
        assertEquals(1, books.get(0).pages().size());
    }

    @Test
    void keepsMultiplePagesInOneBookWhenAllowed() {
        String text = String.join("\n", Collections.nCopies(30, "x"));
        List<PlannedBook> books = BookPlanner.plan(job(2, text), ONE_PIXEL);
        assertEquals(2, books.size());
        assertEquals(2, books.get(0).pages().size());
        assertEquals(1, books.get(1).pages().size());
    }

    @Test
    void numbersBooksContinuouslyAcrossSegments() {
        JobManifest job = new JobManifest();
        job.version = 1;
        job.titleBase = "T";
        job.pageLimit = 1;
        String text = String.join("\n", Collections.nCopies(30, "x"));
        job.segments = List.of(segment(1, text), segment(2, text));

        List<PlannedBook> books = BookPlanner.plan(job, ONE_PIXEL);

        assertEquals(6, books.size());
        assertEquals(List.of("T-01", "T-02", "T-03", "T-04", "T-05", "T-06"),
            books.stream().map(PlannedBook::title).toList());
        assertEquals(1, books.get(2).segmentIndex());
        assertEquals(2, books.get(3).segmentIndex());
        assertEquals(2, books.get(5).segmentIndex());
    }

    @Test
    void packsPagesAcrossSegmentsUpToPageLimit() {
        JobManifest job = new JobManifest();
        job.version = 1;
        job.titleBase = "T";
        job.pageLimit = 6;
        String text = String.join("\n", Collections.nCopies(30, "x"));
        job.segments = List.of(segment(1, text), segment(2, text));

        List<PlannedBook> books = BookPlanner.plan(job, ONE_PIXEL);

        assertEquals(1, books.size());
        assertEquals("T-01", books.get(0).title());
        assertEquals(6, books.get(0).pages().size());
        assertEquals(1, books.get(0).segmentIndex());
    }

    @Test
    void packsAcrossSegmentsAndSplitsRemainder() {
        JobManifest job = new JobManifest();
        job.version = 1;
        job.titleBase = "T";
        job.pageLimit = 5;
        String text = String.join("\n", Collections.nCopies(30, "x"));
        job.segments = List.of(segment(1, text), segment(2, text));

        List<PlannedBook> books = BookPlanner.plan(job, ONE_PIXEL);

        assertEquals(2, books.size());
        assertEquals(5, books.get(0).pages().size());
        assertEquals(1, books.get(1).pages().size());
    }

    @Test
    void breaksBookAtSentenceWhenEnabled() {
        JobManifest job = new JobManifest();
        job.version = 1;
        job.titleBase = "T";
        job.pageLimit = 5;
        job.segments = List.of(segment(
            1,
            pagesText("end.", "middle", "end!", "middle", "middle", "middle")
        ));

        List<PlannedBook> books = BookPlanner.plan(job, ONE_PIXEL, 0, true);

        assertEquals(2, books.size());
        assertEquals(3, books.get(0).pages().size());
        assertEquals(3, books.get(1).pages().size());
        assertTrue(SentenceBreaks.endsAtSentence(books.get(0).pages().get(2)));
    }

    @Test
    void splitsAtLimitWhenSentenceBreakDisabled() {
        JobManifest job = new JobManifest();
        job.version = 1;
        job.titleBase = "T";
        job.pageLimit = 5;
        job.segments = List.of(segment(
            1,
            pagesText("end.", "middle", "end!", "middle", "middle", "middle")
        ));

        List<PlannedBook> books = BookPlanner.plan(job, ONE_PIXEL, 0, false);

        assertEquals(2, books.size());
        assertEquals(5, books.get(0).pages().size());
        assertEquals(1, books.get(1).pages().size());
    }

    @Test
    void overridesPageLimitFromConfig() {
        JobManifest job = new JobManifest();
        job.version = 1;
        job.titleBase = "T";
        job.pageLimit = 100;
        String text = String.join("\n", Collections.nCopies(30, "x"));
        job.segments = List.of(segment(1, text));

        List<PlannedBook> books = BookPlanner.plan(job, ONE_PIXEL, 2, false);

        assertEquals(2, books.size());
        assertEquals(2, books.get(0).pages().size());
        assertEquals(1, books.get(1).pages().size());
    }

    private static String pagesText(String... lastLines) {
        List<String> lines = new ArrayList<>();
        for (String lastLine : lastLines) {
            lines.addAll(Collections.nCopies(13, "line"));
            lines.add(lastLine);
        }
        return String.join("\n", lines);
    }

    private static JobSegment segment(int index, String text) {
        JobSegment segment = new JobSegment();
        segment.index = index;
        segment.chapter = index + ". test";
        segment.text = text;
        return segment;
    }
}
