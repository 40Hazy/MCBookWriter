package com.mcbookwriter.autobook.layout;

import java.util.List;

public record PlannedBook(int segmentIndex, String chapter, String title, List<String> pages) {
}
