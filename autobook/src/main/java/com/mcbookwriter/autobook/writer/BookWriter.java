package com.mcbookwriter.autobook.writer;

import com.mcbookwriter.autobook.AutoBookClient;
import com.mcbookwriter.autobook.compat.ClientCompat;
import com.mcbookwriter.autobook.compat.ScreenCompat;
import com.mcbookwriter.autobook.config.AutoBookConfig;
import com.mcbookwriter.autobook.layout.PlannedBook;
import com.mcbookwriter.autobook.progress.PlanDigest;
import com.mcbookwriter.autobook.progress.RunState;
import com.mcbookwriter.autobook.progress.StateStore;
import com.mcbookwriter.autobook.verify.ContentVerifier;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.inventory.BookEditScreen;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ServerboundEditBookPacket;
import net.minecraft.network.protocol.game.ServerboundSetCarriedItemPacket;
import net.minecraft.server.network.Filterable;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.WrittenBookContent;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public final class BookWriter {
    public enum State {
        IDLE,
        SETTLE,
        FIND_BOOK,
        WAIT_FOR_INVENTORY,
        USE_BOOK,
        CLOSE_BOOK_SCREEN,
        WRITE,
        WAIT_FOR_CONFIRM,
        RETRY_WAIT,
        RECOVERY_WAIT,
        PAUSED,
        DONE,
        ERROR
    }

    private enum PauseKind {
        NONE,
        MANUAL,
        SUPPLY,
        CONFIRM,
        VERIFY
    }

    private enum RecoveryPhase {
        NONE,
        LONG_WAIT,
        CLOSE_WAIT
    }

    private static final BookWriter INSTANCE = new BookWriter();
    private static final int USE_BOOK_WAIT_TICKS = 5;
    private static final int SCREEN_WAIT_TICKS = 10;
    private static final int SUPPLY_CHECK_TICKS = 20;
    private static final int RECOVERY_CLOSE_WAIT_TICKS = 30;
    private static final int MAX_WRITE_ATTEMPTS = 3;

    private final List<PlannedBook> books = new ArrayList<>();
    private final StateStore stateStore = StateStore.defaultStore();
    private State state = State.IDLE;
    private PlannedBook current;
    private String jobName = "";
    private String sourceHash = "";
    private String planHash = "";
    private int index;
    private int completedBooks;
    private int verifiedBooks;
    private int totalPages;
    private boolean keepWrittenBooks = true;
    private boolean skipExistingBooks = true;
    private boolean verifyContent = true;
    private boolean autoRecover = true;
    private int recoveryWaitTicks = 200;
    private int settleTicks = 15;
    private int inventoryWaitTicks = 80;
    private int confirmWaitTicks = 100;
    private int retryDelayTicks = 120;
    private int maxInventoryRetries = 3;
    private boolean pauseRequested;
    private boolean forceWriteCurrent;
    private boolean recoveryUsed;
    private boolean closeOnly;
    private RecoveryPhase recoveryPhase = RecoveryPhase.NONE;
    private PauseKind pauseKind = PauseKind.NONE;
    private State resumeTarget = State.SETTLE;
    private int supplyCheckTicks;
    private int waitTicks;
    private int screenTicks;
    private int inventoryAttempts;
    private int writeAttempts;
    private int targetSelectedSlot = -1;
    private String status = "空闲";
    private String lastActionBar = "";

    private BookWriter() {
    }

    public static BookWriter get() {
        return INSTANCE;
    }

    public record Progress(
        String jobName,
        int nextIndex,
        int completedBooks,
        int verifiedBooks,
        int totalBooks,
        int totalPages,
        State state
    ) {
    }

    public void start(
        String jobName,
        String sourceHash,
        List<PlannedBook> plan,
        boolean resume,
        Boolean verifyContentOverride
    ) {
        if (plan.isEmpty()) {
            stop();
            state = State.ERROR;
            status = "没有可写内容";
            return;
        }

        String hash = PlanDigest.hash(jobName, plan);
        RunState restored = null;
        if (resume) {
            try {
                restored = stateStore.load(hash);
            } catch (IOException error) {
                throw new IllegalStateException("读取进度失败: " + error.getMessage(), error);
            }
            if (restored == null || restored.nextIndex <= 0) {
                throw new IllegalStateException("没有找到可恢复的进度，请使用 /autobook start " + jobName);
            }
            if (restored.nextIndex >= plan.size()) {
                throw new IllegalStateException("该任务已经全部完成，请使用 /autobook start " + jobName);
            }
        }

        AutoBookConfig config = AutoBookConfig.get();
        closeBookScreenIfOpen(Minecraft.getInstance());
        books.clear();
        books.addAll(plan);
        this.jobName = jobName;
        this.sourceHash = sourceHash == null ? "" : sourceHash;
        this.planHash = hash;
        this.keepWrittenBooks = config.keepWrittenBooks;
        this.skipExistingBooks = config.skipExistingBooks;
        this.verifyContent = verifyContentOverride != null ? verifyContentOverride : config.verifyContent;
        this.autoRecover = config.autoRecover;
        this.recoveryWaitTicks = clamp(config.recoveryWaitTicks, 20, 1200);
        this.settleTicks = clamp(config.settleTicks, 1, 400);
        this.inventoryWaitTicks = clamp(config.inventoryWaitTicks, 20, 600);
        this.confirmWaitTicks = clamp(config.confirmWaitTicks, 20, 600);
        this.retryDelayTicks = clamp(config.retryDelayTicks, 20, 1200);
        this.maxInventoryRetries = clamp(config.maxInventoryRetries, 1, 10);
        this.totalPages = plan.stream().mapToInt(book -> book.pages().size()).sum();
        this.index = restored == null ? 0 : restored.nextIndex;
        this.completedBooks = restored == null ? 0 : Math.min(restored.completedBooks, this.index);
        this.verifiedBooks = restored == null ? 0 : Math.min(restored.verifiedBooks, this.index);
        this.current = plan.get(index);
        this.pauseRequested = false;
        this.forceWriteCurrent = restored != null && restored.forceRewrite;
        this.recoveryUsed = false;
        this.closeOnly = false;
        this.recoveryPhase = RecoveryPhase.NONE;
        this.pauseKind = PauseKind.NONE;
        this.supplyCheckTicks = 0;
        this.waitTicks = settleTicks;
        this.screenTicks = 0;
        this.inventoryAttempts = 0;
        this.writeAttempts = 0;
        this.targetSelectedSlot = -1;
        this.lastActionBar = "";
        this.state = State.SETTLE;
        this.status = "准备写入 " + current.title();
        saveState();
        AutoBookClient.LOG.info(
            "AutoBook: {} '{}' at book {}/{} ({} pages total)",
            resume ? "resume" : "start",
            jobName,
            index + 1,
            books.size(),
            totalPages
        );
    }

    public void stop() {
        closeBookScreenIfOpen(Minecraft.getInstance());
        if (!books.isEmpty() && state != State.IDLE) {
            saveState();
        }
        state = State.IDLE;
        current = null;
        books.clear();
        jobName = "";
        sourceHash = "";
        planHash = "";
        index = 0;
        completedBooks = 0;
        verifiedBooks = 0;
        totalPages = 0;
        pauseRequested = false;
        forceWriteCurrent = false;
        recoveryUsed = false;
        closeOnly = false;
        recoveryPhase = RecoveryPhase.NONE;
        pauseKind = PauseKind.NONE;
        supplyCheckTicks = 0;
        waitTicks = 0;
        screenTicks = 0;
        inventoryAttempts = 0;
        writeAttempts = 0;
        targetSelectedSlot = -1;
        status = "已停止";
        lastActionBar = "";
    }

    public boolean pause() {
        if (state == State.IDLE || state == State.DONE || state == State.ERROR || state == State.PAUSED) {
            return false;
        }
        if (state == State.SETTLE || state == State.FIND_BOOK) {
            enterPause(PauseKind.MANUAL, "已暂停", state);
            return true;
        }
        pauseRequested = true;
        status = "将在当前书完成后暂停";
        return true;
    }

    public boolean resume() {
        if (state != State.PAUSED) {
            return false;
        }
        pauseKind = PauseKind.NONE;
        pauseRequested = false;
        writeAttempts = 0;
        inventoryAttempts = 0;
        screenTicks = 0;
        waitTicks = 0;
        recoveryUsed = false;
        closeOnly = false;
        recoveryPhase = RecoveryPhase.NONE;
        state = resumeTarget;
        status = "继续写入 " + (current == null ? "" : current.title());
        return true;
    }

    public Progress progress() {
        return new Progress(jobName, index, completedBooks, verifiedBooks, books.size(), totalPages, state);
    }

    public String status() {
        return displayText();
    }

    public void tick(Minecraft client) {
        if (state == State.IDLE || state == State.DONE || state == State.ERROR) {
            showStatus(client);
            return;
        }
        if (state == State.PAUSED) {
            handlePaused(client);
            showStatus(client);
            return;
        }
        if (client.player == null || client.level == null) {
            return;
        }

        if (ScreenCompat.current(client) != null) {
            if (ScreenCompat.current(client) instanceof BookEditScreen) {
                if (state != State.CLOSE_BOOK_SCREEN) {
                    closeBookScreenIfOpen(client);
                }
            } else if (needsClosedScreen(state)) {
                status = "等待关闭界面";
                showStatus(client);
                return;
            }
        }

        if (pauseRequested && (state == State.SETTLE || state == State.FIND_BOOK)) {
            pauseRequested = false;
            enterPause(PauseKind.MANUAL, "已暂停", state);
            showStatus(client);
            return;
        }

        switch (state) {
            case SETTLE -> settle();
            case FIND_BOOK -> findBook(client);
            case WAIT_FOR_INVENTORY -> waitForInventory(client);
            case USE_BOOK -> useBook(client);
            case CLOSE_BOOK_SCREEN -> closeBookScreen(client);
            case WRITE -> write(client);
            case WAIT_FOR_CONFIRM -> confirm(client);
            case RETRY_WAIT -> retryWait();
            case RECOVERY_WAIT -> recoveryWait();
            default -> {
            }
        }
        showStatus(client);
    }

    private static boolean needsClosedScreen(State state) {
        return switch (state) {
            case SETTLE, FIND_BOOK, WAIT_FOR_INVENTORY, USE_BOOK, RETRY_WAIT, RECOVERY_WAIT -> true;
            default -> false;
        };
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private void settle() {
        if (waitTicks-- > 0) {
            return;
        }
        state = State.FIND_BOOK;
        status = "查找空的书与笔";
    }

    private void retryWait() {
        if (waitTicks-- > 0) {
            return;
        }
        state = State.FIND_BOOK;
        status = "重新检查书本";
    }

    private void recoveryWait() {
        if (waitTicks-- > 0) {
            return;
        }
        if (recoveryPhase == RecoveryPhase.LONG_WAIT) {
            recoveryPhase = RecoveryPhase.CLOSE_WAIT;
            closeOnly = true;
            state = State.USE_BOOK;
            status = "自动恢复: 重新打开书本页面";
            AutoBookClient.LOG.info("AutoBook: recovery cycle, opening and closing the book screen");
            return;
        }
        recoveryPhase = RecoveryPhase.NONE;
        closeOnly = false;
        state = State.USE_BOOK;
        status = "自动恢复: 重新写入";
        AutoBookClient.LOG.info("AutoBook: recovery cycle finished, writing again");
    }

    private void handlePaused(Minecraft client) {
        if (pauseKind != PauseKind.SUPPLY || client.player == null) {
            return;
        }
        if (supplyCheckTicks-- > 0) {
            return;
        }
        supplyCheckTicks = SUPPLY_CHECK_TICKS;
        if (InventoryHelper.findEmptyBook(client.player.getInventory()) != null) {
            pauseKind = PauseKind.NONE;
            state = State.FIND_BOOK;
            waitTicks = 0;
            status = "检测到空的书与笔，继续";
            AutoBookClient.LOG.info("AutoBook: empty book supplied, continuing");
        }
    }

    private void findBook(Minecraft client) {
        if (client.player == null || client.gameMode == null) {
            return;
        }

        Inventory inventory = client.player.getInventory();

        if (skipExistingBooks && !forceWriteCurrent && InventoryHelper.hasWrittenBook(
            inventory,
            current.title(),
            current.pages().size()
        )) {
            AutoBookClient.LOG.info("AutoBook: '{}' already signed, skipping", current.title());
            if (!keepWrittenBooks && InventoryHelper.isWrittenBook(
                inventory.getSelectedItem(),
                current.title(),
                current.pages().size()
            )) {
                dropSelectedBook(client);
            }
            advanceAfterBook(client, false);
            return;
        }

        InventoryHelper.BookSlot book = InventoryHelper.findEmptyBook(inventory);
        if (book == null) {
            if (InventoryHelper.hasEmptyBookInOffhand(inventory)) {
                enterPause(
                    PauseKind.SUPPLY,
                    "空书在副手，请移到快捷栏或背包后自动继续",
                    State.FIND_BOOK
                );
            } else {
                enterPause(PauseKind.SUPPLY, "缺少空的书与笔，补给后自动继续", State.FIND_BOOK);
            }
            return;
        }

        int selected = inventory.getSelectedSlot();
        if (book.inventorySlot() == selected) {
            targetSelectedSlot = selected;
            state = State.USE_BOOK;
            status = "使用书本";
            AutoBookClient.LOG.info("AutoBook: book already in selected slot {}", selected);
            return;
        }

        if (book.inventorySlot() < 9) {
            targetSelectedSlot = book.inventorySlot();
            inventory.setSelectedSlot(book.inventorySlot());
            client.player.connection.send(new ServerboundSetCarriedItemPacket(book.inventorySlot()));
            AutoBookClient.LOG.info(
                "AutoBook: selecting hotbar slot {} (was {})",
                book.inventorySlot(),
                selected
            );
        } else {
            int hotbarTarget = findEmptyHotbarSlot(inventory, selected);
            targetSelectedSlot = hotbarTarget;
            if (selected != hotbarTarget) {
                inventory.setSelectedSlot(hotbarTarget);
                client.player.connection.send(new ServerboundSetCarriedItemPacket(hotbarTarget));
            }
            ClientCompat.containerInput(
                client.gameMode,
                client.player.inventoryMenu.containerId,
                book.menuSlot(),
                hotbarTarget,
                "SWAP",
                client.player
            );
            AutoBookClient.LOG.info(
                "AutoBook: swapping inventory slot {} to hotbar slot {}",
                book.inventorySlot(),
                hotbarTarget
            );
        }

        waitTicks = inventoryWaitTicks;
        state = State.WAIT_FOR_INVENTORY;
        status = "移动空书到主手";
    }

    private static int findEmptyHotbarSlot(Inventory inventory, int fallback) {
        for (int slot = 0; slot < 9; slot++) {
            if (inventory.getItem(slot).isEmpty()) {
                return slot;
            }
        }
        return fallback;
    }

    private void waitForInventory(Minecraft client) {
        if (client.player == null) {
            return;
        }
        Inventory inventory = client.player.getInventory();
        boolean selectedReady = inventory.getSelectedSlot() == targetSelectedSlot;
        boolean itemReady = InventoryHelper.isWritableBook(inventory.getSelectedItem());

        if (selectedReady && itemReady) {
            inventoryAttempts = 0;
            state = State.USE_BOOK;
            status = "使用书本";
            return;
        }

        if (waitTicks-- > 0) {
            return;
        }

        inventoryAttempts++;
        AutoBookClient.LOG.warn(
            "AutoBook: empty book not ready (selected={}, expected={}, item={}, attempt {}/{})",
            inventory.getSelectedSlot(),
            targetSelectedSlot,
            inventory.getSelectedItem().getItem(),
            inventoryAttempts,
            maxInventoryRetries
        );
        if (inventoryAttempts < maxInventoryRetries) {
            state = State.FIND_BOOK;
            status = "空书未就位，重新整理 (" + inventoryAttempts + "/" + maxInventoryRetries + ")";
        } else {
            inventoryAttempts = 0;
            enterPause(
                PauseKind.MANUAL,
                "无法把空书移到主手，请整理背包后 /autobook resume",
                State.FIND_BOOK
            );
        }
    }

    private void useBook(Minecraft client) {
        if (client.player == null || client.gameMode == null) {
            return;
        }
        Inventory inventory = client.player.getInventory();
        if (inventory.getSelectedItem().is(Items.WRITTEN_BOOK)) {
            WrittenBookContent handContent = inventory.getSelectedItem().get(DataComponents.WRITTEN_BOOK_CONTENT);
            if (handContent != null && current.title().equals(handContent.title().raw())) {
                if (verifySignedBook(client)) {
                    completeBook(client);
                }
                return;
            }
        }
        if (!InventoryHelper.isWritableBook(inventory.getSelectedItem())) {
            fail("主手不是空的书与笔");
            return;
        }

        client.gameMode.useItem(client.player, InteractionHand.MAIN_HAND);
        waitTicks = USE_BOOK_WAIT_TICKS;
        screenTicks = SCREEN_WAIT_TICKS;
        state = State.CLOSE_BOOK_SCREEN;
        status = "关闭书本页面";
        AutoBookClient.LOG.info("AutoBook: used held book (attempt {}/{})", writeAttempts + 1, MAX_WRITE_ATTEMPTS);
    }

    private void closeBookScreen(Minecraft client) {
        if (waitTicks-- > 0) {
            return;
        }
        if (ScreenCompat.current(client) instanceof BookEditScreen) {
            closeBookScreenIfOpen(client);
            finishBookScreenClose();
            return;
        }
        if (screenTicks-- > 0) {
            return;
        }
        AutoBookClient.LOG.info("AutoBook: book screen did not open, writing anyway");
        finishBookScreenClose();
    }

    private void finishBookScreenClose() {
        if (closeOnly) {
            closeOnly = false;
            recoveryPhase = RecoveryPhase.CLOSE_WAIT;
            waitTicks = RECOVERY_CLOSE_WAIT_TICKS;
            state = State.RECOVERY_WAIT;
            status = "自动恢复: 书本页面已关闭";
            return;
        }
        enterWriteState();
    }

    private void enterWriteState() {
        state = State.WRITE;
        status = "写入 " + current.title();
    }

    private void write(Minecraft client) {
        if (client.player == null) {
            return;
        }
        Inventory inventory = client.player.getInventory();
        if (!InventoryHelper.isWritableBook(inventory.getSelectedItem())) {
            fail("主手不是空的书与笔");
            return;
        }

        closeBookScreenIfOpen(client);
        writeAttempts++;
        setLocalWrittenContent(client);
        client.player.connection.send(new ServerboundEditBookPacket(
            inventory.getSelectedSlot(),
            current.pages(),
            Optional.of(current.title())
        ));
        waitTicks = confirmWaitTicks;
        state = State.WAIT_FOR_CONFIRM;
        status = "写入 " + current.title() + " (尝试 " + writeAttempts + "/" + MAX_WRITE_ATTEMPTS + ")";
        AutoBookClient.LOG.info(
            "AutoBook: sent '{}' attempt {}/{} with {} pages (client prediction enabled)",
            current.title(),
            writeAttempts,
            MAX_WRITE_ATTEMPTS,
            current.pages().size()
        );
    }

    private void confirm(Minecraft client) {
        if (waitTicks-- > 0) {
            return;
        }
        if (client.player == null) {
            return;
        }

        Inventory inventory = client.player.getInventory();
        var hand = inventory.getSelectedItem();
        boolean signed = hand.is(Items.WRITTEN_BOOK)
            || (skipExistingBooks && !forceWriteCurrent && InventoryHelper.hasWrittenBook(
                inventory,
                current.title(),
                current.pages().size()
            ));

        if (signed) {
            if (verifySignedBook(client)) {
                completeBook(client);
            }
            return;
        }

        if (InventoryHelper.isWritableBook(hand)) {
            if (writeAttempts < MAX_WRITE_ATTEMPTS) {
                state = State.RETRY_WAIT;
                waitTicks = Math.min(retryDelayTicks * writeAttempts, 600);
                status = "服务器退回空书，准备重试 " + current.title();
                AutoBookClient.LOG.warn("AutoBook: server reverted '{}' to writable, retrying", current.title());
                return;
            }
            if (autoRecover && !recoveryUsed) {
                recoveryUsed = true;
                writeAttempts = 0;
                recoveryPhase = RecoveryPhase.LONG_WAIT;
                waitTicks = recoveryWaitTicks;
                state = State.RECOVERY_WAIT;
                status = "自动恢复: 等待 " + (recoveryWaitTicks / 20) + " 秒后重试";
                AutoBookClient.LOG.warn("AutoBook: starting automatic recovery for '{}'", current.title());
                return;
            }
            enterPause(
                PauseKind.CONFIRM,
                "服务器未确认 " + current.title() + "，请手动右键打开并关闭本书后 /autobook resume",
                State.SETTLE
            );
            AutoBookClient.LOG.warn(
                "AutoBook: no confirmation for '{}' after {} attempts, paused",
                current.title(),
                writeAttempts
            );
            return;
        }

        fail("服务器没有确认 " + current.title() + " (attempts=" + writeAttempts + ", hand=" + hand.getItem() + ")");
    }

    private boolean verifySignedBook(Minecraft client) {
        if (!verifyContent) {
            return true;
        }
        Inventory inventory = client.player.getInventory();
        WrittenBookContent content = handSignedContent(inventory);
        if (content == null) {
            content = InventoryHelper.findWrittenContent(inventory, current.title());
        }
        if (content == null) {
            enterPause(PauseKind.VERIFY, "无法读取成书内容，请检查本书后 /autobook resume", State.SETTLE);
            return false;
        }

        List<String> actual = content.pages().stream()
            .map(page -> page.raw().getString())
            .toList();
        ContentVerifier.Result result = ContentVerifier.verify(current.pages(), actual);
        if (result.ok()) {
            verifiedBooks = Math.max(verifiedBooks, index + 1);
            AutoBookClient.LOG.info(
                "AutoBook: verified '{}' ({} pages, sha256={})",
                current.title(),
                result.actualPages(),
                result.expectedDigest()
            );
            return true;
        }

        forceWriteCurrent = true;
        AutoBookClient.LOG.warn(
            "AutoBook: verification failed for '{}': expected pages={}, actual pages={}, "
                + "first mismatch page={}, expected='{}', actual='{}', "
                + "expected sha256={}, actual sha256={}",
            current.title(),
            result.expectedPages(),
            result.actualPages(),
            result.firstMismatchPage(),
            result.expectedPreview(),
            result.actualPreview(),
            result.expectedDigest(),
            result.actualDigest()
        );
        enterPause(
            PauseKind.VERIFY,
            "内容校验失败: " + current.title() + " 第 " + result.firstMismatchPage()
                + " 页，请移除该书后 /autobook resume",
            State.SETTLE
        );
        return false;
    }

    private WrittenBookContent handSignedContent(Inventory inventory) {
        var hand = inventory.getSelectedItem();
        if (!hand.is(Items.WRITTEN_BOOK)) {
            return null;
        }
        WrittenBookContent content = hand.get(DataComponents.WRITTEN_BOOK_CONTENT);
        if (content == null || !current.title().equals(content.title().raw())) {
            return null;
        }
        return content;
    }

    private void completeBook(Minecraft client) {
        advanceAfterBook(client, true);
    }

    private void advanceAfterBook(Minecraft client, boolean signedNow) {
        completedBooks = index + 1;
        AutoBookClient.LOG.info(
            "AutoBook: {} '{}' ({}/{})",
            signedNow ? "completed" : "already signed, skipped",
            current.title(),
            completedBooks,
            books.size()
        );

        index++;
        forceWriteCurrent = false;
        saveState();
        if (signedNow && !keepWrittenBooks) {
            dropSelectedBook(client);
        }

        writeAttempts = 0;
        inventoryAttempts = 0;
        targetSelectedSlot = -1;
        recoveryUsed = false;
        closeOnly = false;
        recoveryPhase = RecoveryPhase.NONE;

        if (index >= books.size()) {
            state = State.DONE;
            status = "全部完成: " + books.size() + " 本, " + totalPages + " 页";
            lastActionBar = "";
            AutoBookClient.LOG.info("AutoBook: job '{}' finished ({} books, {} pages)", jobName, books.size(), totalPages);
            return;
        }

        current = books.get(index);
        if (pauseRequested) {
            pauseRequested = false;
            enterPause(PauseKind.MANUAL, "已暂停", State.SETTLE);
            return;
        }

        waitTicks = settleTicks;
        state = State.SETTLE;
        status = "准备写入 " + current.title();
    }

    private void dropSelectedBook(Minecraft client) {
        if (client.player == null || client.gameMode == null) {
            return;
        }
        if (ScreenCompat.current(client) != null) {
            AutoBookClient.LOG.warn("AutoBook: screen open, keeping written book in inventory");
            return;
        }
        int selected = client.player.getInventory().getSelectedSlot();
        ClientCompat.containerInput(
            client.gameMode,
            client.player.inventoryMenu.containerId,
            36 + selected,
            1,
            "THROW",
            client.player
        );
        AutoBookClient.LOG.info("AutoBook: dropped written book from slot {}", selected);
    }

    private void setLocalWrittenContent(Minecraft client) {
        if (client.player == null) {
            return;
        }
        List<Filterable<Component>> pages = current.pages().stream()
            .map(page -> Filterable.passThrough(Component.nullToEmpty(page)))
            .toList();
        WrittenBookContent content = new WrittenBookContent(
            Filterable.passThrough(current.title()),
            ClientCompat.playerName(client.player),
            0,
            pages,
            true
        );
        client.player.getMainHandItem().set(DataComponents.WRITTEN_BOOK_CONTENT, content);
    }

    private void closeBookScreenIfOpen(Minecraft client) {
        if (ScreenCompat.current(client) instanceof BookEditScreen) {
            ScreenCompat.set(client, null);
            AutoBookClient.LOG.info("AutoBook: closed book edit screen without saving");
        }
    }

    private void enterPause(PauseKind kind, String reason, State resumeTarget) {
        pauseKind = kind;
        this.resumeTarget = resumeTarget;
        state = State.PAUSED;
        status = reason;
        supplyCheckTicks = SUPPLY_CHECK_TICKS;
        saveState();
        AutoBookClient.LOG.info("AutoBook: paused ({}) - {}", kind, reason);
    }

    private void saveState() {
        if (planHash.isEmpty()) {
            return;
        }
        RunState run = new RunState();
        run.version = 1;
        run.jobName = jobName;
        run.sourceHash = sourceHash;
        run.planHash = planHash;
        run.nextIndex = index;
        run.completedBooks = completedBooks;
        run.totalBooks = books.size();
        run.totalPages = totalPages;
        run.verifiedBooks = verifiedBooks;
        run.forceRewrite = forceWriteCurrent;
        run.updatedAt = OffsetDateTime.now().toString();
        try {
            stateStore.save(run);
        } catch (IOException error) {
            AutoBookClient.LOG.warn("AutoBook: failed to save state: {}", error.getMessage());
        }
    }

    private void fail(String reason) {
        closeBookScreenIfOpen(Minecraft.getInstance());
        state = State.ERROR;
        status = "失败: " + reason;
        AutoBookClient.LOG.warn("AutoBook: {}", reason);
    }

    private String displayText() {
        if (books.isEmpty()) {
            return status;
        }
        int shown = state == State.DONE ? books.size() : Math.min(index + 1, books.size());
        return "[" + shown + "/" + books.size() + "] " + status;
    }

    private void showStatus(Minecraft client) {
        if (client.player == null) {
            return;
        }
        String text = displayText();
        if (text.equals(lastActionBar)) {
            return;
        }
        lastActionBar = text;
        ClientCompat.actionBar(client.player, Component.literal(text));
    }
}
