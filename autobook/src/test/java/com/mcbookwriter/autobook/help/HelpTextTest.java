package com.mcbookwriter.autobook.help;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class HelpTextTest {
    @Test
    void overviewListsCoreCommands() {
        List<String> lines = HelpText.lines();

        assertFalse(lines.isEmpty());
        String text = String.join("\n", lines);
        assertTrue(text.contains("/autobook add"));
        assertTrue(text.contains("/autobook stop"));
        assertTrue(text.contains("/autobook help"));
        assertTrue(lines.get(0).startsWith("AutoBook "));
    }

    @Test
    void topicsResolveAndSupportChineseAliases() {
        assertNotNull(HelpText.topicLines("start"));
        assertEquals(HelpText.topicLines("run"), HelpText.topicLines("运行"));
        assertEquals(HelpText.topicLines("cancel"), HelpText.topicLines("取消"));
        assertTrue(String.join("\n", HelpText.topicLines("run")).contains("RUNNING"));
    }

    @Test
    void unknownTopicReturnsNull() {
        assertNull(HelpText.topicLines("missing"));
        assertTrue(HelpText.topicList().contains("verify"));
    }
}
