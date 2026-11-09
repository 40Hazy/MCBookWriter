package com.mcbookwriter.autobook.gui;

import com.terraformersmc.modmenu.api.ConfigScreenFactory;
import com.terraformersmc.modmenu.api.ModMenuApi;

/**
 * Mod Menu 可选集成：未安装 Mod Menu 时该入口不会被请求，本类也不会被加载。
 */
public final class AutoBookModMenuIntegration implements ModMenuApi {
    @Override
    public ConfigScreenFactory<?> getModConfigScreenFactory() {
        return parent -> new AutoBookConfigScreen();
    }
}
