package com.mcbookwriter.autobook.config;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AutoBookConfigTest {
    @Test
    void setUpdatesBooleanAndIntegerFields() {
        AutoBookConfig config = new AutoBookConfig();

        config.set("keepWrittenBooks", "false");
        config.set("verifyContent", "off");
        config.set("pageLimit", "80");
        config.set("maxInventoryRetries", "5");
        config.set("queueStopOnFailure", "true");

        assertFalse(config.keepWrittenBooks);
        assertFalse(config.verifyContent);
        assertEquals(80, config.pageLimit);
        assertEquals(5, config.maxInventoryRetries);
        assertTrue(config.queueStopOnFailure);
    }

    @Test
    void setRejectsUnknownKey() {
        AutoBookConfig config = new AutoBookConfig();

        assertThrows(IllegalArgumentException.class, () -> config.set("unknown", "1"));
    }

    @Test
    void setRejectsOutOfRangeIntegers() {
        AutoBookConfig config = new AutoBookConfig();

        assertThrows(IllegalArgumentException.class, () -> config.set("pageLimit", "101"));
        assertThrows(IllegalArgumentException.class, () -> config.set("settleTicks", "0"));
        assertThrows(IllegalArgumentException.class, () -> config.set("confirmWaitTicks", "not-a-number"));
    }

    @Test
    void setRejectsInvalidBoolean() {
        AutoBookConfig config = new AutoBookConfig();

        assertThrows(IllegalArgumentException.class, () -> config.set("autoRecover", "maybe"));
    }
}
