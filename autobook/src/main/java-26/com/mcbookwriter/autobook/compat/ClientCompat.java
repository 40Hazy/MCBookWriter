package com.mcbookwriter.autobook.compat;

import net.minecraft.client.multiplayer.MultiPlayerGameMode;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ContainerInput;

public final class ClientCompat {
    private ClientCompat() {
    }

    public static void actionBar(Player player, Component text) {
        player.sendOverlayMessage(text);
    }

    public static String playerName(Player player) {
        return player.getGameProfile().name();
    }

    public static void containerInput(
        MultiPlayerGameMode mode,
        int containerId,
        int slot,
        int button,
        String action,
        Player player
    ) {
        ContainerInput input = switch (action) {
            case "SWAP" -> ContainerInput.SWAP;
            case "THROW" -> ContainerInput.THROW;
            default -> throw new IllegalArgumentException("Unknown container action: " + action);
        };
        mode.handleContainerInput(containerId, slot, button, input, player);
    }
}
