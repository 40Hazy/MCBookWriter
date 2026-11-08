package com.mcbookwriter.autobook.layout;

import com.mcbookwriter.autobook.job.JobManifest;
import com.mcbookwriter.autobook.job.JobSegment;

import java.util.ArrayList;
import java.util.List;

public final class BookPlanner {
    private static final int MAX_TITLE_LENGTH = 32;
    private static final double MIN_FILL_RATIO = 0.6;

    private BookPlanner() {
    }

    public static List<PlannedBook> plan(JobManifest job, WidthProvider widthProvider) {
        return plan(job, widthProvider, 0, false);
    }

    public static List<PlannedBook> plan(
        JobManifest job,
        WidthProvider widthProvider,
        int pageLimitOverride,
        boolean breakAtSentence
    ) {
        int limit = effectiveLimit(job.pageLimit, pageLimitOverride);
        int searchWindow = Math.min(20, Math.max(5, limit / 5));
        int minPages = Math.max(1, (int) Math.ceil(limit * MIN_FILL_RATIO));

        List<PlannedBook> books = new ArrayList<>();
        List<PageRef> buffer = new ArrayList<>();
        int globalIndex = 1;

        for (JobSegment segment : job.segments) {
            List<String> pages = PageLayout.paginate(segment.text, widthProvider);
            for (String page : pages) {
                buffer.add(new PageRef(page, segment.index, segment.chapter));
                if (buffer.size() > limit) {
                    int end = breakAtSentence
                        ? findBoundary(buffer, limit, searchWindow, minPages)
                        : limit;
                    books.add(createBook(job.titleBase, globalIndex++, buffer, end));
                    buffer = new ArrayList<>(buffer.subList(end, buffer.size()));
                }
            }
        }

        if (!buffer.isEmpty()) {
            books.add(createBook(job.titleBase, globalIndex, buffer, buffer.size()));
        }

        return books;
    }

    private static int effectiveLimit(int jobLimit, int override) {
        int limit = override > 0 ? override : jobLimit;
        return Math.max(1, Math.min(100, limit));
    }

    private static int findBoundary(List<PageRef> buffer, int limit, int searchWindow, int minPages) {
        int min = Math.max(minPages, limit - searchWindow);
        for (int end = limit; end >= min; end--) {
            if (SentenceBreaks.endsAtSentence(buffer.get(end - 1).text())
                && !SentenceBreaks.startsWithCloser(buffer.get(end).text())) {
                return end;
            }
        }
        return limit;
    }

    private static PlannedBook createBook(String titleBase, int index, List<PageRef> pages, int end) {
        String title = String.format("%s-%02d", titleBase, index);
        if (title.length() > MAX_TITLE_LENGTH) {
            throw new IllegalArgumentException("Book title exceeds 32 characters: " + title);
        }

        List<String> texts = new ArrayList<>(end);
        for (int i = 0; i < end; i++) {
            texts.add(pages.get(i).text());
        }
        PageRef first = pages.get(0);
        return new PlannedBook(first.segmentIndex(), first.chapter(), title, List.copyOf(texts));
    }

    private record PageRef(String text, int segmentIndex, String chapter) {
    }
}
