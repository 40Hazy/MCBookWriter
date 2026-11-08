package com.mcbookwriter.autobook.compat;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Gui;
import net.minecraft.client.gui.screens.Screen;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

/**
 * 26.1.x 把当前界面保存在 Minecraft.screen，26.2 移到了 Gui.screen()。
 * 这里用反射兼容两套 API，避免为 26.2 复制一份界面代码。
 */
public final class ScreenCompat {
    private static final Method GUI_SCREEN = guiMethod("screen");
    private static final Method GUI_SET_SCREEN = guiMethod("setScreen", Screen.class);
    private static final Field MC_SCREEN = mcField("screen");
    private static final Method MC_SET_SCREEN = mcMethod("setScreen", Screen.class);

    private ScreenCompat() {
    }

    public static Screen current(Minecraft client) {
        if (GUI_SCREEN != null) {
            return (Screen) invoke(GUI_SCREEN, client.gui);
        }
        if (MC_SCREEN != null) {
            try {
                return (Screen) MC_SCREEN.get(client);
            } catch (ReflectiveOperationException exception) {
                throw new IllegalStateException("读取当前界面失败", exception);
            }
        }
        return null;
    }

    public static void set(Minecraft client, Screen screen) {
        if (GUI_SET_SCREEN != null) {
            invoke(GUI_SET_SCREEN, client.gui, screen);
            return;
        }
        if (MC_SET_SCREEN != null) {
            invoke(MC_SET_SCREEN, client, screen);
            return;
        }
        throw new IllegalStateException("当前 Minecraft 版本不支持界面切换");
    }

    private static Method guiMethod(String name, Class<?>... parameters) {
        try {
            return Gui.class.getMethod(name, parameters);
        } catch (NoSuchMethodException exception) {
            return null;
        }
    }

    private static Method mcMethod(String name, Class<?>... parameters) {
        try {
            return Minecraft.class.getMethod(name, parameters);
        } catch (NoSuchMethodException exception) {
            return null;
        }
    }

    private static Field mcField(String name) {
        try {
            return Minecraft.class.getField(name);
        } catch (NoSuchFieldException exception) {
            return null;
        }
    }

    private static Object invoke(Method method, Object target, Object... arguments) {
        try {
            return method.invoke(target, arguments);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("调用界面方法失败: " + method.getName(), exception);
        }
    }
}
