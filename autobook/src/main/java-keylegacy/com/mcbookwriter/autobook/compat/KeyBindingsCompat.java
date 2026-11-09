package com.mcbookwriter.autobook.compat;

import com.mojang.blaze3d.platform.InputConstants;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.minecraft.client.KeyMapping;

/** 1.21.x：按键分类以语言键字符串传入。 */
public final class KeyBindingsCompat {
    private KeyBindingsCompat() {
    }

    public static KeyMapping register(String name, int keyCode, String categoryKey) {
        return KeyBindingHelper.registerKeyBinding(new KeyMapping(
            name,
            InputConstants.Type.KEYSYM,
            keyCode,
            categoryKey
        ));
    }
}
