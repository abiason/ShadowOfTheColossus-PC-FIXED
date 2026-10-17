// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_overlay.h"

#include <atomic>
#include <cfloat>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <mutex>

#include <SDL3/SDL.h>
#include "bbport_settings.h"
#include "video_core/sotc_stats.h"
#include <string>
#include <vector>
#include "imgui.h"
#include "imgui_impl_vulkan.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"

// DejaVu Sans (Cyrillic), embedded (third_party/fonts, Bitstream Vera license).
#ifdef _WIN32
asm(".section .rdata,\"dr\"\n"
    ".balign 16\n"
    ".global bb_font_ttf\n"
    "bb_font_ttf:\n"
    ".incbin \"" BB_FONT_PATH "\"\n"
    ".global bb_font_ttf_end\n"
    "bb_font_ttf_end:\n"
    ".text\n");
#else
asm(".section .rodata\n"
    ".balign 16\n"
    ".hidden bb_font_ttf\n"
    ".global bb_font_ttf\n"
    "bb_font_ttf:\n"
    ".incbin \"" BB_FONT_PATH "\"\n"
    ".hidden bb_font_ttf_end\n"
    ".global bb_font_ttf_end\n"
    "bb_font_ttf_end:\n"
    ".previous\n");
#endif
extern "C" const unsigned char bb_font_ttf[];
extern "C" const unsigned char bb_font_ttf_end[];

namespace BbOverlay {

namespace {

std::mutex imgui_mutex; // the ImGui context: window thread (input) and present thread
bool initialized = false;
// The game's text dialog (SetTextEntry), guarded by imgui_mutex.
bool text_entry_active = false;
std::string text_entry_prompt, text_entry_text;
// The game's save/load slot list (OpenSaveList), guarded by imgui_mutex.
bool list_active = false;
std::string list_title;
std::vector<std::string> list_items;
int list_selected = 0, list_result = -1;
int list_confirm = -1;  // item waiting for the delete confirmation, or -1
int list_first_deletable = 0;
bool list_scroll = false, list_stick_down = false, list_stick_up = false;
float base_scale = 1.0f;

// Present rate for the FPS counter.
std::chrono::steady_clock::time_point last_present{};
float frame_ms_avg = 0.0f;
// sotc: frame times of the last ~2 s (1% low) and the command count per frame.
std::vector<float> recent_ms;
size_t recent_next = 0;
float low_fps = 0.0f, cmds_per_frame = 0.0f;
u64 last_commands = 0;

// sotc: the in-game menu (Insert on the keyboard, L2+R3 on the gamepad), guarded by imgui_mutex.
bool menu_open = false;
int menu_row = 0;
bool left_trigger_held = false;
enum MenuRow { RowFps, RowStats, RowFsr, RowRcas, RowVibration, RowClose, RowCount };

/// Launcher language (SOTC_UI_LANG: es, pt, en).
const char* T(const char* es, const char* pt, const char* en) {
    static const int lang = [] { // 0 es, 1 pt, 2 en
        const char* v = std::getenv("SOTC_UI_LANG");
        if (v && v[0] == 'e' && v[1] == 's') return 0;
        if (v && v[0] == 'p' && v[1] == 't') return 1;
        return 2;
    }();
    return lang == 0 ? es : lang == 1 ? pt : en;
}

std::string MenuFile() {
    const char* dir = std::getenv("BB_GPU_USER_DIR");
    return std::string(dir ? dir : ".") + "/ingame_menu.ini";
}

void SaveMenu() {
    const auto& v = BbSettings::Get();
    if (FILE* f = std::fopen(MenuFile().c_str(), "w")) {
        std::fprintf(f, "show_fps=%d\nshow_stats=%d\n", int(v.show_fps.load()), int(v.show_stats.load()));
        std::fclose(f);
    }
}

void LoadMenu() {
    auto& v = BbSettings::Get();
    if (FILE* f = std::fopen(MenuFile().c_str(), "r")) {
        int a = 0;
        char line[128];
        while (std::fgets(line, sizeof(line), f)) {
            if (std::sscanf(line, "show_fps=%d", &a) == 1) v.show_fps = a != 0;
            if (std::sscanf(line, "show_stats=%d", &a) == 1) v.show_stats = a != 0;
        }
        std::fclose(f);
    }
}

int EnvInt(const char* name, int fallback) {
    const char* v = std::getenv(name);
    return v && *v ? std::atoi(v) : fallback;
}

/// Effective values: the menu's override or what the launcher started the game with.
bool FsrOn() {
    const int v = BbSettings::Get().sotc_fsr1.load();
    return v >= 0 ? v != 0 : EnvInt("BB_FSR1", 1) != 0;
}
int RcasLevel() { // 0 off, 1 low, 2 medium, 3 high
    int v = BbSettings::Get().sotc_rcas.load();
    if (v < 0) {
        v = EnvInt("BB_RCAS", 1) ? EnvInt("BB_RCAS_ATTENUATION", 250) : 1000;
    }
    return v >= 1000 ? 0 : v >= 200 ? 1 : v >= 100 ? 2 : 3;
}
int Vibration() {
    const int v = BbSettings::Get().vibration.load();
    return v >= 0 ? v : std::clamp(EnvInt("SOTC_VIBRATION", 100), 0, 100);
}

void ChangeRow(int row, int dir) {
    auto& v = BbSettings::Get();
    switch (row) {
    case RowFps:
        v.show_fps = !v.show_fps;
        SaveMenu();
        break;
    case RowStats:
        v.show_stats = !v.show_stats;
        if (v.show_stats) v.show_fps = true;
        SaveMenu();
        break;
    case RowFsr:
        v.sotc_fsr1 = FsrOn() ? 0 : 1;
        break;
    case RowRcas: {
        static constexpr int levels[] = {1000, 250, 150, 50};
        v.sotc_rcas = levels[(RcasLevel() + (dir < 0 ? 3 : 1)) % 4];
        break;
    }
    case RowVibration:
        v.vibration = std::clamp(Vibration() + dir * 10, 0, 100);
        break;
    case RowClose:
        menu_open = false;
        break;
    }
}

void ToggleMenu() {
    menu_open = !menu_open;
    menu_row = 0;
}

float PixelDensity(SDL_WindowID id) {
    SDL_Window* window = SDL_GetWindowFromID(id);
    const float density = window ? SDL_GetWindowPixelDensity(window) : 1.0f;
    return density > 0.0f ? density : 1.0f;
}

// The game's text dialog: what is typed, and how to finish (keyboard or controller).
void TextEntryBox() {
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + viewport->WorkSize.x * 0.5f,
                                   viewport->WorkPos.y + viewport->WorkSize.y * 0.42f),
                            ImGuiCond_Always, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSizeConstraints(ImVec2(viewport->WorkSize.x * 0.32f, 0.0f),
                                        ImVec2(viewport->WorkSize.x * 0.8f, FLT_MAX));
    ImGui::SetNextWindowBgAlpha(0.92f);
    ImGui::Begin("##text_entry", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                     ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                     ImGuiWindowFlags_NoFocusOnAppearing);
    ImGui::TextColored(ImVec4(0.85f, 0.72f, 0.45f, 1.0f), "%s", text_entry_prompt.c_str());
    ImGui::Separator();
    ImGui::SetWindowFontScale(1.4f);
    ImGui::Text("%s_", text_entry_text.c_str());
    ImGui::SetWindowFontScale(1.0f);
    ImGui::Separator();
    ImGui::TextDisabled("Keyboard: type, Backspace to erase, Enter = OK, Esc = cancel");
    ImGui::TextDisabled("Controller: Cross (A) = OK, Circle (B) = cancel");
    ImGui::End();
}

// The game's save/load slot list: one entry per save, the selected one highlighted.
void SaveListBox() {
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + viewport->WorkSize.x * 0.5f,
                                   viewport->WorkPos.y + viewport->WorkSize.y * 0.5f),
                            ImGuiCond_Always, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSize(ImVec2(viewport->WorkSize.x * 0.46f, viewport->WorkSize.y * 0.62f),
                             ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.94f);
    ImGui::Begin("##save_list", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoNav |
                     ImGuiWindowFlags_NoSavedSettings);
    ImGui::SetWindowFontScale(1.25f);
    ImGui::PushTextWrapPos(0.0f); // sotc: save dialog messages are whole sentences
    ImGui::TextColored(ImVec4(0.85f, 0.72f, 0.45f, 1.0f), "%s", list_title.c_str());
    ImGui::PopTextWrapPos();
    ImGui::SetWindowFontScale(1.0f);
    ImGui::Separator();
    const float footer = ImGui::GetTextLineHeightWithSpacing() * 2.2f;
    ImGui::BeginChild("##items", ImVec2(0.0f, -footer));
    for (int i = 0; i < static_cast<int>(list_items.size()); ++i) {
        ImGui::PushID(i);
        const bool selected = i == list_selected;
        if (ImGui::Selectable(list_items[i].c_str(), selected,
                              ImGuiSelectableFlags_AllowDoubleClick)) {
            list_selected = i;
            if (ImGui::IsMouseDoubleClicked(0)) {
                list_result = i;
            }
        }
        if (selected && list_scroll) {
            ImGui::SetScrollHereY(0.5f);
        }
        ImGui::Separator();
        ImGui::PopID();
    }
    list_scroll = false;
    ImGui::EndChild();
    ImGui::Separator();
    if (list_confirm >= 0) {
        ImGui::TextColored(ImVec4(1.0f, 0.45f, 0.35f, 1.0f),
                           "Apagar este save?   Enter / X (A): sim    Esc / O (B): nao");
    } else if (list_first_deletable >= static_cast<int>(list_items.size())) { // sotc: YES/NO
        ImGui::TextDisabled("Setas / direcional: escolher    Enter / X (A): confirmar    "
                            "Esc / O (B): nao");
    } else {
        ImGui::TextDisabled("Setas / direcional: escolher    Enter / X (A): confirmar    "
                            "Esc / O (B): voltar    Del / Triangulo (Y): apagar");
    }
    ImGui::End();
}

void FpsCounter() {
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    const float pad = 12.0f * base_scale;
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + viewport->WorkSize.x - pad,
                                   viewport->WorkPos.y + pad),
                            ImGuiCond_Always, ImVec2(1.0f, 0.0f));
    ImGui::SetNextWindowBgAlpha(0.5f);
    ImGui::Begin("##fps", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                     ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                     ImGuiWindowFlags_NoFocusOnAppearing);
    ImGui::Text("%.0f FPS  %.1f ms", frame_ms_avg > 0.0f ? 1000.0f / frame_ms_avg : 0.0f,
                frame_ms_avg);
    if (BbSettings::Get().show_stats) {
        ImGui::Text("1%% low %.0f FPS", low_fps);
        ImGui::Text("%.0f %s", cmds_per_frame, T("comandos/fotograma", "comandos/quadro", "commands/frame"));
    }
    ImGui::End();
}

void MenuBox() {
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + 40.0f * base_scale, viewport->WorkPos.y + 40.0f * base_scale),
                            ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.88f);
    ImGui::Begin("##sotc_menu", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoNav |
                     ImGuiWindowFlags_NoFocusOnAppearing);
    ImGui::TextColored(ImVec4(0.84f, 0.75f, 0.54f, 1.0f), "Shadow of the Colossus — %s", T("menú del port", "menu do port", "port menu"));
    ImGui::Text("%.0f FPS   %.1f ms   1%% low %.0f   %.0f %s", frame_ms_avg > 0.0f ? 1000.0f / frame_ms_avg : 0.0f,
                frame_ms_avg, low_fps, cmds_per_frame, T("comandos", "comandos", "commands"));
    ImGui::Separator();
    static const char* rcas_names_es[] = {"No", "Baja", "Media", "Alta"};
    static const char* rcas_names_pt[] = {"Não", "Baixa", "Média", "Alta"};
    static const char* rcas_names_en[] = {"Off", "Low", "Medium", "High"};
    const auto onoff = [](bool on) { return on ? T("Sí", "Sim", "On") : T("No", "Não", "Off"); };
    const auto& v = BbSettings::Get();
    char vib[16];
    std::snprintf(vib, sizeof(vib), "%d%%", Vibration());
    const char* rcas = T(rcas_names_es[RcasLevel()], rcas_names_pt[RcasLevel()], rcas_names_en[RcasLevel()]);
    const std::pair<const char*, const char*> rows[RowCount] = {
        {T("Mostrar FPS", "Mostrar FPS", "Show FPS"), onoff(v.show_fps)},
        {T("Estadísticas detalladas", "Estatísticas detalhadas", "Detailed statistics"), onoff(v.show_stats)},
        {T("Escalado FSR 1 (salida > 1080p)", "Escala FSR 1 (saída > 1080p)", "FSR 1 upscaling (output > 1080p)"), onoff(FsrOn())},
        {T("Nitidez (RCAS)", "Nitidez (RCAS)", "Sharpening (RCAS)"), rcas},
        {T("Vibración", "Vibração", "Vibration"), vib},
        {T("Volver al juego", "Voltar ao jogo", "Back to the game"), ""},
    };
    for (int r = 0; r < RowCount; ++r) {
        const bool sel = r == menu_row;
        ImGui::TextColored(sel ? ImVec4(0.84f, 0.75f, 0.54f, 1.0f) : ImVec4(0.9f, 0.89f, 0.85f, 1.0f),
                           "%s %-36s %s", sel ? ">" : " ", rows[r].first,
                           rows[r].second[0] ? (std::string("< ") + rows[r].second + " >").c_str() : "");
    }
    ImGui::Separator();
    ImGui::TextDisabled("%s", T("↑↓ elegir   ←→ cambiar   Insert / L2+R3 / Esc / Círculo: cerrar",
                                "↑↓ escolher   ←→ mudar   Insert / L2+R3 / Esc / Círculo: fechar",
                                "Up/Down choose   Left/Right change   Insert / L2+R3 / Esc / Circle: close"));
    ImGui::TextDisabled("%s", T("Los demás ajustes se cambian en el lanzador.",
                                "Os outros ajustes ficam no lançador.", "Other settings are in the launcher."));
    ImGui::End();
}

} // namespace

void Init(const Vulkan::Instance& instance, vk::Format format, u32 image_count) {
    std::scoped_lock lock{imgui_mutex};
    if (initialized) {
        return;
    }
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr; // window positions are not kept
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard | ImGuiConfigFlags_NavEnableGamepad;
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
    io.BackendPlatformName = "bbport";

    ImGui::StyleColorsDark();
    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowRounding = 6.0f;
    style.FrameRounding = 4.0f;
    style.GrabRounding = 4.0f;
    style.Colors[ImGuiCol_WindowBg].w = 0.92f;

    ImFontConfig font_config;
    font_config.FontDataOwnedByAtlas = false;
    io.Fonts->AddFontFromMemoryTTF(const_cast<unsigned char*>(bb_font_ttf),
                                   int(bb_font_ttf_end - bb_font_ttf), 18.0f, &font_config);

    const vk::Instance vk_instance = instance.GetInstance();
    ImGui_ImplVulkan_LoadFunctions(
        instance.ApiVersion(),
        [](const char* name, void* user) {
            return VULKAN_HPP_DEFAULT_DISPATCHER.vkGetInstanceProcAddr(
                *static_cast<const vk::Instance*>(user), name);
        },
        const_cast<vk::Instance*>(&vk_instance));

    const VkFormat color_format = static_cast<VkFormat>(format);
    ImGui_ImplVulkan_InitInfo info{};
    info.ApiVersion = instance.ApiVersion();
    info.Instance = vk_instance;
    info.PhysicalDevice = instance.GetPhysicalDevice();
    info.Device = instance.GetDevice();
    info.QueueFamily = instance.GetGraphicsQueueFamilyIndex();
    info.Queue = instance.GetGraphicsQueue();
    info.DescriptorPoolSize = 16;
    info.MinImageCount = std::max(image_count, 2u);
    info.ImageCount = std::max(image_count, 2u);
    info.UseDynamicRendering = true;
    info.PipelineInfoMain.PipelineRenderingCreateInfo = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO_KHR,
        .colorAttachmentCount = 1,
        .pColorAttachmentFormats = &color_format,
    };
    if (!ImGui_ImplVulkan_Init(&info)) {
        std::printf("Overlay: ImGui Vulkan backend init failed\n");
        ImGui::DestroyContext();
        return;
    }
    initialized = true;
    LoadMenu();
    std::printf("Overlay: ready\n");
}

// The menu has no text fields: SDL text input stays as the game's text dialog sets it (window.cpp).
void UpdateTextInput(SDL_Window*) {}

bool HandleEvent(const SDL_Event& event) {
    std::scoped_lock lock{imgui_mutex};
    if (!initialized) {
        return false;
    }
    ImGuiIO& io = ImGui::GetIO();
    // sotc: the in-game menu opens with Insert or L2+R3 and takes the input while open.
    if (event.type == SDL_EVENT_GAMEPAD_AXIS_MOTION && event.gaxis.axis == SDL_GAMEPAD_AXIS_LEFT_TRIGGER) {
        left_trigger_held = event.gaxis.value > 16000;
    }
    if (!list_active && !text_entry_active) {
        if ((event.type == SDL_EVENT_KEY_DOWN && event.key.key == SDLK_INSERT && !event.key.repeat) ||
            (event.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN && event.gbutton.button == SDL_GAMEPAD_BUTTON_RIGHT_STICK &&
             left_trigger_held)) {
            ToggleMenu();
            return true;
        }
        if (menu_open) {
            int key = 0; // 1 up, 2 down, 3 left, 4 right, 5 accept, 6 close
            if (event.type == SDL_EVENT_KEY_DOWN) {
                switch (event.key.key) {
                case SDLK_UP: case SDLK_W: key = 1; break;
                case SDLK_DOWN: case SDLK_S: key = 2; break;
                case SDLK_LEFT: case SDLK_A: key = 3; break;
                case SDLK_RIGHT: case SDLK_D: key = 4; break;
                case SDLK_RETURN: case SDLK_KP_ENTER: case SDLK_SPACE: key = event.key.repeat ? 0 : 5; break;
                case SDLK_ESCAPE: case SDLK_BACKSPACE: key = 6; break;
                default: break;
                }
            } else if (event.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN) {
                switch (event.gbutton.button) {
                case SDL_GAMEPAD_BUTTON_DPAD_UP: key = 1; break;
                case SDL_GAMEPAD_BUTTON_DPAD_DOWN: key = 2; break;
                case SDL_GAMEPAD_BUTTON_DPAD_LEFT: key = 3; break;
                case SDL_GAMEPAD_BUTTON_DPAD_RIGHT: key = 4; break;
                case SDL_GAMEPAD_BUTTON_SOUTH: key = 5; break;
                case SDL_GAMEPAD_BUTTON_EAST: case SDL_GAMEPAD_BUTTON_START: key = 6; break;
                default: break;
                }
            }
            switch (key) {
            case 1: menu_row = (menu_row + RowCount - 1) % RowCount; break;
            case 2: menu_row = (menu_row + 1) % RowCount; break;
            case 3: ChangeRow(menu_row, -1); break;
            case 4: case 5: ChangeRow(menu_row, 1); break;
            case 6: menu_open = false; break;
            default: break;
            }
            // While open, keys, buttons and the mouse are the menu's, not the game's.
            switch (event.type) {
            case SDL_EVENT_KEY_DOWN: case SDL_EVENT_KEY_UP: case SDL_EVENT_GAMEPAD_BUTTON_DOWN:
            case SDL_EVENT_GAMEPAD_BUTTON_UP: case SDL_EVENT_GAMEPAD_AXIS_MOTION:
                return true;
            default:
                break;
            }
        }
    }
    if (list_active && list_result == -1) {
        const int count = static_cast<int>(list_items.size());
        const auto move = [&](int delta) {
            list_confirm = -1;
            if (count) {
                list_selected = (list_selected + delta + count) % count;
                list_scroll = true;
            }
        };
        switch (event.type) {
        case SDL_EVENT_KEY_DOWN:
            switch (event.key.key) {
            case SDLK_UP:
            case SDLK_W:
                move(-1);
                break;
            case SDLK_DOWN:
            case SDLK_S:
                move(1);
                break;
            case SDLK_RETURN:
            case SDLK_KP_ENTER:
            case SDLK_SPACE:
                if (!event.key.repeat && list_confirm >= 0) {
                    list_result = -100 - list_confirm; // delete it (PollSaveList)
                    list_confirm = -1;
                } else if (!event.key.repeat && count) {
                    list_result = list_selected;
                }
                break;
            case SDLK_ESCAPE:
            case SDLK_BACKSPACE:
                if (!event.key.repeat) {
                    if (list_confirm >= 0) {
                        list_confirm = -1;
                    } else {
                        list_result = -2;
                    }
                }
                break;
            case SDLK_DELETE:
                if (!event.key.repeat && list_selected >= list_first_deletable &&
                    list_selected < count) {
                    list_confirm = list_selected;
                }
                break;
            default:
                break;
            }
            return true;
        case SDL_EVENT_KEY_UP:
        case SDL_EVENT_TEXT_INPUT:
            return true;
        case SDL_EVENT_GAMEPAD_BUTTON_DOWN:
            switch (event.gbutton.button) {
            case SDL_GAMEPAD_BUTTON_DPAD_UP:
                move(-1);
                break;
            case SDL_GAMEPAD_BUTTON_DPAD_DOWN:
                move(1);
                break;
            case SDL_GAMEPAD_BUTTON_SOUTH:
                if (list_confirm >= 0) {
                    list_result = -100 - list_confirm;
                    list_confirm = -1;
                } else if (count) {
                    list_result = list_selected;
                }
                break;
            case SDL_GAMEPAD_BUTTON_EAST:
                if (list_confirm >= 0) {
                    list_confirm = -1;
                } else {
                    list_result = -2;
                }
                break;
            case SDL_GAMEPAD_BUTTON_NORTH:
                if (list_selected >= list_first_deletable && list_selected < count) {
                    list_confirm = list_selected;
                }
                break;
            default:
                break;
            }
            return true;
        case SDL_EVENT_GAMEPAD_BUTTON_UP:
            return true;
        case SDL_EVENT_GAMEPAD_AXIS_MOTION:
            if (event.gaxis.axis == SDL_GAMEPAD_AXIS_LEFTY) {
                const bool down = event.gaxis.value > 20000, up = event.gaxis.value < -20000;
                if (down && !list_stick_down) {
                    move(1);
                }
                if (up && !list_stick_up) {
                    move(-1);
                }
                list_stick_down = down;
                list_stick_up = up;
            }
            return true;
        case SDL_EVENT_MOUSE_MOTION: {
            const float density = PixelDensity(event.motion.windowID);
            io.AddMousePosEvent(event.motion.x * density, event.motion.y * density);
            return true;
        }
        case SDL_EVENT_MOUSE_BUTTON_DOWN:
        case SDL_EVENT_MOUSE_BUTTON_UP:
            if (event.button.button == SDL_BUTTON_LEFT) {
                io.AddMouseButtonEvent(0, event.type == SDL_EVENT_MOUSE_BUTTON_DOWN);
            }
            return true;
        case SDL_EVENT_MOUSE_WHEEL:
            io.AddMouseWheelEvent(event.wheel.x, event.wheel.y);
            return true;
        default:
            break;
        }
    }
    return false;
}

bool Visible() {
    return initialized && (text_entry_active || list_active || menu_open || BbSettings::Get().show_fps);
}

bool CapturesInput() {
    return text_entry_active || list_active || menu_open;
}

bool OpenSaveList(const std::string& title, const std::vector<std::string>& items, int focus,
                  int first_deletable) {
    std::scoped_lock lock{imgui_mutex};
    if (!initialized) {
        return false; // nothing could show it
    }
    list_title = title;
    list_items = items;
    list_selected = items.empty() ? 0 : std::clamp(focus, 0, static_cast<int>(items.size()) - 1);
    list_result = -1;
    list_confirm = -1;
    list_first_deletable = first_deletable < 0 ? static_cast<int>(items.size()) : first_deletable;
    list_scroll = true;
    list_active = true;
    ImGui::GetIO().MouseDrawCursor = true;
    return true;
}

int PollSaveList() {
    std::scoped_lock lock{imgui_mutex};
    if (!list_active || list_result == -1) {
        return -1;
    }
    list_active = false;
    if (initialized) {
        ImGui::GetIO().MouseDrawCursor = false;
    }
    return list_result;
}

void CloseSaveList() {
    std::scoped_lock lock{imgui_mutex};
    list_active = false;
    if (initialized) {
        ImGui::GetIO().MouseDrawCursor = false;
    }
}

void SetTextEntry(bool active, const std::string& prompt, const std::string& text) {
    std::scoped_lock lock{imgui_mutex};
    text_entry_active = active;
    text_entry_prompt = prompt;
    text_entry_text = text;
}

void Render(vk::CommandBuffer cmdbuf, vk::ImageView view, vk::Extent2D extent) {
    // Present interval for the FPS readout (measured also while nothing is drawn).
    const auto now = std::chrono::steady_clock::now();
    const float ms = std::chrono::duration<float, std::milli>(now - last_present).count();
    last_present = now;
    if (ms > 0.0f && ms < 1000.0f) {
        frame_ms_avg = frame_ms_avg == 0.0f ? ms : frame_ms_avg * 0.95f + ms * 0.05f;
        // sotc: 1% low over the last 120 frames, command count per frame.
        if (recent_ms.size() < 120) {
            recent_ms.push_back(ms);
        } else {
            recent_ms[recent_next] = ms;
            recent_next = (recent_next + 1) % recent_ms.size();
        }
        if (recent_next % 30 == 0) {
            auto sorted = recent_ms;
            std::sort(sorted.begin(), sorted.end());
            const float worst = sorted[std::min(sorted.size() - 1, size_t(sorted.size() * 0.99))];
            low_fps = worst > 0.0f ? 1000.0f / worst : 0.0f;
        }
        const u64 commands = SotcStats::commands.load(std::memory_order_relaxed);
        cmds_per_frame = cmds_per_frame * 0.9f + float(commands - last_commands) * 0.1f;
        last_commands = commands;
    }
    if (!Visible()) {
        return;
    }
    std::scoped_lock lock{imgui_mutex};
    ImGuiIO& io = ImGui::GetIO();
    io.DisplaySize = ImVec2(float(extent.width), float(extent.height));
    io.DeltaTime = ms > 0.0f && ms < 1000.0f ? ms / 1000.0f : 1.0f / 60.0f;
    // UI scale follows the display height (1080p = 1).
    const float scale = std::max(float(extent.height) / 1080.0f, 0.75f);
    if (std::abs(scale - base_scale) > 0.01f) {
        ImGuiStyle& style = ImGui::GetStyle();
        style.ScaleAllSizes(scale / base_scale);
        style.FontScaleMain = scale;
        base_scale = scale;
    }

    ImGui_ImplVulkan_NewFrame();
    ImGui::NewFrame();
    if (BbSettings::Get().show_fps) {
        FpsCounter();
    }
    if (menu_open) {
        MenuBox();
    }
    if (text_entry_active) {
        TextEntryBox();
    }
    if (list_active) {
        SaveListBox();
    }
    ImGui::Render();

    const vk::RenderingAttachmentInfo attachment{
        .imageView = view,
        .imageLayout = vk::ImageLayout::eColorAttachmentOptimal,
        .loadOp = vk::AttachmentLoadOp::eLoad,
        .storeOp = vk::AttachmentStoreOp::eStore,
    };
    cmdbuf.beginRendering(vk::RenderingInfo{
        .renderArea = {{0, 0}, extent},
        .layerCount = 1,
        .colorAttachmentCount = 1,
        .pColorAttachments = &attachment,
    });
    {
        // Font atlas uploads submit to the graphics queue themselves.
        std::scoped_lock submit_lock{Vulkan::Scheduler::submit_mutex};
        ImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), cmdbuf);
    }
    cmdbuf.endRendering();
}

} // namespace BbOverlay
