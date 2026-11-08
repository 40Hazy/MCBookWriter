package com.mcbookwriter.autobook.verify;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ContentVerifierTest {
    @Test
    void acceptsIdenticalPages() {
        ContentVerifier.Result result = ContentVerifier.verify(
            List.of("第一页", "第二页"),
            List.of("第一页", "第二页")
        );

        assertTrue(result.ok());
        assertEquals(2, result.expectedPages());
        assertEquals(2, result.actualPages());
    }

    @Test
    void detectsMissingPages() {
        ContentVerifier.Result result = ContentVerifier.verify(
            List.of("一", "二", "三"),
            List.of("一", "二")
        );

        assertFalse(result.ok());
        assertEquals(3, result.firstMismatchPage());
    }

    @Test
    void detectsTruncatedPage() {
        ContentVerifier.Result result = ContentVerifier.verify(
            List.of("完整的一句话。"),
            List.of("完整的一句")
        );

        assertFalse(result.ok());
        assertEquals(1, result.firstMismatchPage());
        assertEquals("完整的一句话。", result.expectedPreview());
    }

    @Test
    void ignoresFormattingCodesAndTrailingSpaces() {
        ContentVerifier.Result result = ContentVerifier.verify(
            List.of("第一行\n第二行"),
            List.of("§a第一行   \r\n第二行 §r")
        );

        assertTrue(result.ok());
    }

    @Test
    void digestIgnoresFormattingAndMatchesIdenticalPages() {
        String planned = ContentVerifier.digest(List.of("第一页", "第二页"));
        String written = ContentVerifier.digest(List.of("§a第一页 ", "第二页\r"));

        assertEquals(planned, written);
        assertEquals(64, planned.length());
    }

    @Test
    void digestChangesWhenPageContentChanges() {
        String planned = ContentVerifier.digest(List.of("完整的一句话。"));
        String written = ContentVerifier.digest(List.of("完整的一句"));

        assertFalse(planned.equals(written));
    }

    @Test
    void resultCarriesWholeBookDigests() {
        ContentVerifier.Result result = ContentVerifier.verify(
            List.of("一", "二"),
            List.of("一", "三")
        );

        assertFalse(result.ok());
        assertEquals(ContentVerifier.digest(List.of("一", "二")), result.expectedDigest());
        assertEquals(ContentVerifier.digest(List.of("一", "三")), result.actualDigest());
        assertFalse(result.expectedDigest().equals(result.actualDigest()));
    }
}
