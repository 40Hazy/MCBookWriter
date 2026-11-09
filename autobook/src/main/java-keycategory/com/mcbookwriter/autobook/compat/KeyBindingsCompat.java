package com.mcbookwriter.autobook.compat;

import com.mojang.blaze3d.platform.InputConstants;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.minecraft.client.KeyMapping;
import net.minecraft.resources.Identifier;

/** 1.21.11：分类改为 Category，Fabric 模块仍为 fabric-key-binding-api-v1。 */
public final class KeyBindingsCompat {
    private static final KeyMapping.Category CATEGORY =
        KeyMapping.Category.register(Identifier.fromNamespaceAndPath("autobook", "general"));

    private KeyBindingsCompat() {
    }

    public static KeyMapping register(String name, int keyCode, String categoryKey) {
        return KeyBindingHelper.registerKeyBinding(new KeyMapping(
            name,
            InputConstants.Type.KEYSYM,
            keyCode,
            CATEGORY
        ));
    }
}
