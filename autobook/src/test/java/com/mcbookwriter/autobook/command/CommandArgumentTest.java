package com.mcbookwriter.autobook.command;

import com.mojang.brigadier.StringReader;
import com.mojang.brigadier.arguments.StringArgumentType;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class CommandArgumentTest {
    @Test
    void greedyStringAcceptsChineseJobName() throws Exception {
        StringReader reader = new StringReader("三体1");
        assertEquals("三体1", StringArgumentType.greedyString().parse(reader));
    }
}
