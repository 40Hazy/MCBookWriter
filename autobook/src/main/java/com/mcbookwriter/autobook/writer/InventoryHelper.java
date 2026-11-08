package com.mcbookwriter.autobook.writer;

import net.minecraft.core.component.DataComponents;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.WritableBookContent;
import net.minecraft.world.item.component.WrittenBookContent;

public final class InventoryHelper {
    private static final int OFFHAND_SLOT = 40;

    private InventoryHelper() {
    }

    public record BookSlot(int inventorySlot) {
        public int menuSlot() {
            return inventorySlot < 9 ? 36 + inventorySlot : inventorySlot;
        }
    }

    public static BookSlot findEmptyBook(Inventory inventory) {
        for (int slot = 0; slot < 36; slot++) {
            if (isWritableBook(inventory.getItem(slot))) {
                return new BookSlot(slot);
            }
        }
        return null;
    }

    public static boolean isWritableBook(ItemStack stack) {
        if (!stack.is(Items.WRITABLE_BOOK)) {
            return false;
        }
        WritableBookContent content = stack.get(DataComponents.WRITABLE_BOOK_CONTENT);
        return content == null || content.pages().isEmpty();
    }

    public static boolean hasEmptyBookInOffhand(Inventory inventory) {
        return inventory.getContainerSize() > OFFHAND_SLOT && isWritableBook(inventory.getItem(OFFHAND_SLOT));
    }

    public static boolean hasWrittenBook(Inventory inventory, String title, int pageCount) {
        for (int slot = 0; slot < inventory.getContainerSize(); slot++) {
            if (isWrittenBook(inventory.getItem(slot), title, pageCount)) {
                return true;
            }
        }
        return false;
    }

    public static WrittenBookContent findWrittenContent(Inventory inventory, String title) {
        for (int slot = 0; slot < inventory.getContainerSize(); slot++) {
            ItemStack stack = inventory.getItem(slot);
            if (!stack.is(Items.WRITTEN_BOOK)) {
                continue;
            }
            WrittenBookContent content = stack.get(DataComponents.WRITTEN_BOOK_CONTENT);
            if (content != null && title.equals(content.title().raw())) {
                return content;
            }
        }
        return null;
    }

    public static boolean isWrittenBook(ItemStack stack, String title, int pageCount) {
        if (!stack.is(Items.WRITTEN_BOOK)) {
            return false;
        }
        WrittenBookContent content = stack.get(DataComponents.WRITTEN_BOOK_CONTENT);
        if (content == null || content.pages().size() != pageCount) {
            return false;
        }
        return title.equals(content.title().raw());
    }
}
