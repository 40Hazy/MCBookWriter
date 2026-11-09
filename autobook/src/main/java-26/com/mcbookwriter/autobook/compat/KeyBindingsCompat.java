package com.mcbookwriter.autobook.compat;

import com.mojang.blaze3d.platform.InputConstants;
import net.fabricmc.fabric.api.client.keymapping.v1.KeyMappingHelper;
import net.minecraft.client.KeyMapping;
import net.minecraft.resources.Identifier;

/** 26.x：分类为 Category 对象，Fabric 模块名改为 fabric-key-mapping-api-v1。 */
public final class KeyBindingsCompat {
    private static final KeyMapping.Category CATEGORY =
        KeyMapping.Category.register(Identifier.fromNamespaceAndPath("autobook", "general"));

    private KeyBindingsCompat() {
    }

    public static KeyMapping register(String name, int keyCode, String categoryKey) {
        return KeyMappingHelper.registerKeyMapping(new KeyMapping(
            name,
            InputConstants.Type.KEYSYM,
            keyCode,
            CATEGORY
        ));
    }
}
