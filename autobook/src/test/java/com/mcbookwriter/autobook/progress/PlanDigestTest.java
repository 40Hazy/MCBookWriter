package com.mcbookwriter.autobook.progress;

import com.mcbookwriter.autobook.layout.PlannedBook;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

class PlanDigestTest {
    private PlannedBook book(String title, List<String> pages) {
        return new PlannedBook(1, "1. test", title, pages);
    }

    @Test
    void samePlanProducesSameHash() {
        List<PlannedBook> first = List.of(
            book("T-01", List.of("alpha", "beta")),
            book("T-02", List.of("gamma"))
        );
        List<PlannedBook> second = List.of(
            book("T-01", List.of("alpha", "beta")),
            book("T-02", List.of("gamma"))
        );

        assertEquals(PlanDigest.hash("T", first), PlanDigest.hash("T", second));
    }

    @Test
    void changedPageContentChangesHash() {
        List<PlannedBook> first = List.of(book("T-01", List.of("alpha")));
        List<PlannedBook> second = List.of(book("T-01", List.of("alpha ")));

        assertNotEquals(PlanDigest.hash("T", first), PlanDigest.hash("T", second));
    }

    @Test
    void changedJobNameChangesHash() {
        List<PlannedBook> plan = List.of(book("T-01", List.of("alpha")));

        assertNotEquals(PlanDigest.hash("T", plan), PlanDigest.hash("T2", plan));
    }
}
