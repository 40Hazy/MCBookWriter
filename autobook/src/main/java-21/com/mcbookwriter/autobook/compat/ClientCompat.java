package com.mcbookwriter.autobook.compat;

import net.minecraft.client.multiplayer.MultiPlayerGameMode;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ClickType;

public final class ClientCompat {
    private ClientCompat() {
    }

    public static void actionBar(Player player, Component text) {
        player.displayClientMessage(text, true);
    }

    public static String playerName(Player player) {
        return player.getName().getString();
    }

    public static void containerInput(
        MultiPlayerGameMode mode,
        int containerId,
        int slot,
        int button,
        String action,
        Player player
    ) {
        ClickType type = switch (action) {
            case "SWAP" -> ClickType.SWAP;
            case "THROW" -> ClickType.THROW;
            default -> throw new IllegalArgumentException("Unknown container action: " + action);
        };
        mode.handleInventoryMouseClick(containerId, slot, button, type, player);
    }
}
