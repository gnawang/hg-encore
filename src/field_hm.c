#include <stddef.h>

#include "../include/bag.h"
#include "../include/config.h"
#include "../include/constants/item.h"
#include "../include/constants/moves.h"
#include "../include/constants/species.h"
#include "../include/item.h"
#include "../include/pokemon.h"
#include "../include/save.h"
#include "../include/script.h"
#include "../include/task.h"
#include "../include/sound.h"
#include "../include/sprite.h"
#include "../include/system.h"
#include "../include/types.h"
#include "../include/window.h"
#include "../include/field_hm.h"

// Encore: field HMs without teaching them.
// When no party Pokémon knows a field HM but the HM is in the bag, a "helpful Pokémon" of a fixed species
// uses it instead. The badge checks stay in the vanilla scripts and field code.
// The rental Pokémon is passed around as party slot HM_RENTAL_SLOT, which the hooks below turn into gHMRentalMon.

#define HEAP_ID_FIELD2 11
#define BADGE_STORM    4

#define RENTAL_LEVEL 30

struct HMRental {
    u16 move;
    u16 item;
    u16 species;
};

static const struct HMRental sHMRentals[] = {
    { MOVE_CUT,        ITEM_HM01, SPECIES_FARFETCHD },
    { MOVE_FLY,        ITEM_HM02, SPECIES_PIDGEOT   },
    { MOVE_SURF,       ITEM_HM03, SPECIES_LAPRAS    },
    { MOVE_STRENGTH,   ITEM_HM04, SPECIES_MACHOKE   },
    { MOVE_WHIRLPOOL,  ITEM_HM05, SPECIES_KINGDRA   },
    { MOVE_ROCK_SMASH, ITEM_HM06, SPECIES_GEODUDE   },
    { MOVE_WATERFALL,  ITEM_HM07, SPECIES_GYARADOS  },
    { MOVE_ROCK_CLIMB, ITEM_HM08, SPECIES_RHYDON    },
};

// kept in static memory because the cut-in and field tasks hold a pointer to it for several frames
struct PartyPokemon gHMRentalMon;

// vanilla functions with no hg-engine declaration
void *LONG_CALL FieldMoveCutIn_New(FieldSystem *fsys, int mode, struct PartyPokemon *mon, u32 playerGender);
BOOL LONG_CALL ScrNative_WaitFieldMoveCutIn(SCRIPTCONTEXT *ctx);
void LONG_CALL SetupNativeScript(SCRIPTCONTEXT *ctx, BOOL (*native)(SCRIPTCONTEXT *ctx));
u32 LONG_CALL PlayerAvatar_GetGender(void *playerAvatar);
void *LONG_CALL FlyTaskData_New(int heapId, FieldSystem *fsys, struct PartyPokemon *mon, u16 partySlot, u16 dest, s16 x, s16 y);
BOOL LONG_CALL Task_FlyInField(TaskManager *taskManager);
BOOL LONG_CALL MapHeader_IsFlyAllowed(u32 mapId);

void *LONG_CALL Save_VarsFlags_Get(void *saveData);
BOOL LONG_CALL Save_VarsFlags_CheckHaveFollower(void *varsFlags);
BOOL LONG_CALL Save_VarsFlags_CheckRocketCostumeFlag(void *varsFlags);
void LONG_CALL ClearWindowTilemapAndCopyToVram(void *window);

// Pokégear functions, overlay 100 (pokegear) and 101 (pokegear_app), both loaded while the map card runs
void LONG_CALL PokegearCursorManager_SetCursorSpritesDrawState(void *cursorManager, u16 spec, BOOL draw);
void LONG_CALL PokegearCursorManager_SetSpecIndexAndCursorPos(void *cursorManager, u16 spec, u16 pos);
u16 LONG_CALL PokegearApp_AppIdToButtonIndex(void *pokegear);
void LONG_CALL PokegearMap_HideMapCursor(void *mapApp);
int LONG_CALL PokegearMap_HandleKeyInput_Main(void *mapApp);
void LONG_CALL PokegearMap_UpdateCursorMovement(void *mapApp);
void LONG_CALL PokegearMap_UpdateSelection(void *mapApp);
int LONG_CALL PokegearMap_GetFlyDestinationAtCoord(void *mapApp, u16 x, u16 y);

// the parts of the vanilla PokegearArgs that Fly uses
struct PokegearArgs {
    u8 isScriptedLaunch;    // 00, 1 for a scripted phone call
    u8 filler_01[7];
    int x;                  // 08, the player's position
    int z;                  // 0C
    u8 filler_10[4];
    BOOL setFlyDestination; // 14
    int mapCursorX;         // 18
    int mapCursorY;         // 1C
    u16 selectedFlyDest;    // 20
};

// the parts of the vanilla PokegearAppData and PokegearMapAppData used here (pret's pokegear_internal.h, pokegear_map_internal.h)
struct PokegearApp {
    u8 filler_00[6];
    u8 cursorInAppSwitchZone;    // 006
    u8 filler_07[0x19];
    struct PokegearArgs *args;   // 020
    void *saveData;              // 024
    u8 filler_28[0x4C];
    void *bgConfig;              // 074
    u8 filler_78[4];
    void *cursorManager;         // 07C
};

struct PokegearMapApp {
    u8 filler_00[0xD];
    u8 type;                     // 00D, 0 for the Pokégear's map card
    u8 curRegion;                // 00E, set only by the Fly map
    u8 filler_0F;
    struct PokegearApp *pokegear;// 010
    u8 filler_14[0x74];
    void *msgData;               // 088, text archive 273
    u8 filler_8C[4];
    String *flavorTextString;    // 090
    u8 filler_94[0x78];
    u16 mapID;                   // 10C, where the player is
    u16 playerGender;            // 10E
    s16 cursorX;                 // 110 (pret's playerX)
    s16 cursorY;                 // 112 (pret's playerY)
    u8 filler_114[0x25];
    u8 flags139;                 // 139, bit 2 is set while the cursor moves
    u8 filler_13A[0x4A];
    GF_BGL_BMPWIN windows[9];    // 184
};

// layout checks against pret, so a wrong filler fails the build
_Static_assert(offsetof(struct PokegearArgs, x) == 0x08, "PokegearArgs.x");
_Static_assert(offsetof(struct PokegearArgs, setFlyDestination) == 0x14, "PokegearArgs.setFlyDestination");
_Static_assert(offsetof(struct PokegearArgs, selectedFlyDest) == 0x20, "PokegearArgs.selectedFlyDest");
_Static_assert(offsetof(struct PokegearApp, args) == 0x20, "PokegearAppData.args");
_Static_assert(offsetof(struct PokegearApp, bgConfig) == 0x74, "PokegearAppData.bgConfig");
_Static_assert(offsetof(struct PokegearApp, cursorManager) == 0x7C, "PokegearAppData.cursorManager");
_Static_assert(offsetof(struct PokegearMapApp, pokegear) == 0x10, "PokegearMapAppData.pokegear");
_Static_assert(offsetof(struct PokegearMapApp, msgData) == 0x88, "PokegearMapAppData.msgData");
_Static_assert(offsetof(struct PokegearMapApp, flavorTextString) == 0x90, "PokegearMapAppData.flavorTextString");
_Static_assert(offsetof(struct PokegearMapApp, mapID) == 0x10C, "PokegearMapAppData.mapID");
_Static_assert(offsetof(struct PokegearMapApp, cursorX) == 0x110, "PokegearMapAppData.playerX");
_Static_assert(offsetof(struct PokegearMapApp, flags139) == 0x139, "PokegearMapAppData flags at 0x139");
_Static_assert(offsetof(struct PokegearMapApp, windows) == 0x184, "PokegearMapAppData.windows");

static const struct HMRental *HMRental_Find(u16 move)
{
    for (u32 i = 0; i < NELEMS(sHMRentals); i++) {
        if (sHMRentals[i].move == move) {
            return &sHMRentals[i];
        }
    }
    return NULL;
}

static int Party_FindMonWithMove(struct Party *party, u16 move)
{
    for (int i = 0; i < party->count; i++) {
        struct PartyPokemon *mon = Party_GetMonByIndex(party, i);
        if (GetMonData(mon, MON_DATA_IS_EGG, NULL)) {
            continue;
        }
        if (GetMonData(mon, MON_DATA_MOVE1, NULL) == move || GetMonData(mon, MON_DATA_MOVE2, NULL) == move
            || GetMonData(mon, MON_DATA_MOVE3, NULL) == move || GetMonData(mon, MON_DATA_MOVE4, NULL) == move) {
            return i;
        }
    }
    return -1;
}

// Scans the TM pocket directly. Bag_HasItem loads the item's data from the ROM to find its pocket, which is
// too slow for GetIdxOfFirstPartyMonWithMove, called every frame in the field.
static BOOL HMRental_IsAvailable(void *saveData, u16 move)
{
    const struct HMRental *rental = HMRental_Find(move);
    if (rental == NULL) {
        return FALSE;
    }
    BAG_DATA *bag = Sav2_Bag_get(saveData);
    for (u32 i = 0; i < NUM_BAG_TMS_HMS; i++) {
        if (bag->TMsHMs[i].id == rental->item && bag->TMsHMs[i].quantity != 0) {
            return TRUE;
        }
    }
    return FALSE;
}

// builds gHMRentalMon for the move, non-shiny
static void HMRental_Prepare(u16 move)
{
    const struct HMRental *rental = HMRental_Find(move);
    PokeParaSet(&gHMRentalMon, rental->species, RENTAL_LEVEL, 0, FALSE, 0, 2, 0);
}

/**
 *  @brief party slot of the Pokémon that uses a field HM: a party Pokémon that knows it, else
 *         HM_RENTAL_SLOT when the HM is in the bag, else PARTY_SIZE (6), which the vanilla scripts treat as none
 */
u16 FieldHM_GetUser(void *saveData, u16 move)
{
    int slot = Party_FindMonWithMove(SaveData_GetPlayerPartyPtr(saveData), move);
    if (slot >= 0) {
        return slot;
    }
    if (HMRental_IsAvailable(saveData, move)) {
        HMRental_Prepare(move);
        return HM_RENTAL_SLOT;
    }
    return 6;
}

static struct PartyPokemon *FieldHM_GetMon(void *saveData, u16 slot)
{
    if (slot == HM_RENTAL_SLOT) {
        return &gHMRentalMon;
    }
    return Party_GetMonByIndex(SaveData_GetPlayerPartyPtr(saveData), slot);
}

// hook (arm9 020542E8): field_control.c asks this before offering Surf, and every frame about Waterfall. Only Surf
// checks the bag; checking it every frame for Waterfall slowed the overworld. Callers only compare the result to 0xFF.
int LONG_CALL GetIdxOfFirstPartyMonWithMove(struct Party *party, u16 move)
{
    int slot = Party_FindMonWithMove(party, move);
    if (slot >= 0) {
        return slot;
    }
    if (move == MOVE_SURF && HMRental_IsAvailable(SaveBlock2_get(), move)) {
        return HM_RENTAL_SLOT;
    }
    return 0xFF;
}

// hook (arm9 02043724): script command 183, the field move cut-in, reads the Pokémon from a party slot
BOOL LONG_CALL ScrCmd_183(SCRIPTCONTEXT *ctx)
{
    void **work = FieldSysGetAttrAddr(ctx->fsys, 21);
    u16 slot = VarGet(ctx->fsys, ScriptReadHalfword(ctx));
    struct PartyPokemon *mon = FieldHM_GetMon(ctx->fsys->savedata, slot);
    *work = FieldMoveCutIn_New(ctx->fsys, 0, mon, PlayerAvatar_GetGender(ctx->fsys->playerAvatar));
    SetupNativeScript(ctx, ScrNative_WaitFieldMoveCutIn);
    return TRUE;
}

// hook (overlay 1 021F3100): the Surf, Waterfall, Whirlpool and Rock Climb field tasks read the Pokémon here
struct PartyPokemon *LONG_CALL ov01_021F3100(FieldSystem *fsys, u16 slot)
{
    return FieldHM_GetMon(fsys->savedata, slot);
}

// Fly from the Pokégear's map card. Pressing A on a town the player can fly to closes the Pokégear with the
// destination set, as the Fly map does, and Task_StartMenu_HandleReturn_Pokegear flies there with a party Pokémon
// that knows Fly or a helpful Pidgeot. A small window in the map card's header says "A: Fly here" over those towns.

#define PAD_BUTTON_A 0x0001
#define PAD_BUTTON_B 0x0002

#define SEQ_SE_GS_GEARCANCEL 2368
#define SEQ_SE_GS_GEARDECIDE 2369

#define GEAR_RETURN_EXIT       4 // pret's GEAR_RETURN_4, closes the Pokégear
#define START_MENU_STATE_RETURN 15
#define START_MENU_STATE_RUN_TASK 12

#define BG_LAYER_SUB_1           5
#define FONT_SYSTEM              0
#define MSG_POKEGEAR_FLY_PROMPT  118 // added to data/text/273.txt

// the prompt window, in the empty right side of the region name bar, on tiles below the card's own windows
#define PROMPT_X     18
#define PROMPT_Y     8
#define PROMPT_W     11
#define PROMPT_H     3
#define PROMPT_TILES 0x2AD

static struct {
    struct PokegearMapApp *mapApp;
    GF_BGL_BMPWIN window;
    u8 created;
    u8 shown;
    u8 flyAllowed;
    u32 lastFrame;
} sFlyPrompt;

static BOOL PokegearFly_IsAllowed(struct PokegearMapApp *mapApp)
{
    struct PokegearApp *pokegear = mapApp->pokegear;
    void *saveData = pokegear->saveData;
    void *varsFlags = Save_VarsFlags_Get(saveData);

    return mapApp->type == 0
        && pokegear->args->isScriptedLaunch == 0
        && PlayerProfile_TestBadgeFlag(Sav2_PlayerData_GetProfileAddr(saveData), BADGE_STORM)
        && FieldHM_GetUser(saveData, MOVE_FLY) != 6
        && MapHeader_IsFlyAllowed(mapApp->mapID)
        && !Save_VarsFlags_CheckHaveFollower(varsFlags)
        && !Save_VarsFlags_CheckRocketCostumeFlag(varsFlags);
}

// Pokegear_RegionFromCoords: 0 Kanto, 1 Indigo Plateau and Victory Road, 2 Johto
static u8 PokegearFly_RegionFromCoords(int x, int y)
{
    if (x > 21) {
        if (x == 25 && y == 8) {
            return 2; // Mt. Silver
        }
        if ((x == 28 && y == 6) || (x == 28 && y > 8 && y < 13)) {
            return 1;
        }
        return 0;
    }
    return 2;
}

// The fly destination under the cursor, or 0. As on the Fly map, only towns in the player's region count, or any
// from Indigo Plateau. The check reads curRegion, which only the Fly map sets, so it's set here for the call.
static int PokegearFly_DestinationAtCursor(struct PokegearMapApp *mapApp)
{
    struct PokegearArgs *args = mapApp->pokegear->args;
    u8 savedRegion = mapApp->curRegion;
    mapApp->curRegion = PokegearFly_RegionFromCoords(args->x / 32, args->z / 32);
    int dest = PokegearMap_GetFlyDestinationAtCoord(mapApp, mapApp->cursorX, mapApp->cursorY - 2);
    mapApp->curRegion = savedRegion;
    return dest;
}

static void PokegearFly_UpdatePrompt(struct PokegearMapApp *mapApp)
{
    if (!sFlyPrompt.created || sFlyPrompt.mapApp != mapApp) {
        AddWindowParameterized(mapApp->pokegear->bgConfig, &sFlyPrompt.window, BG_LAYER_SUB_1, PROMPT_X, PROMPT_Y, PROMPT_W, PROMPT_H, 1, PROMPT_TILES);
        FillWindowPixelBuffer(&sFlyPrompt.window, 0);
        sFlyPrompt.mapApp = mapApp;
        sFlyPrompt.created = TRUE;
        sFlyPrompt.shown = FALSE;
        sFlyPrompt.flyAllowed = PokegearFly_IsAllowed(mapApp);
    }

    // Marking mode repaints the top screen, and this handler doesn't run meanwhile, so redraw after any pause
    BOOL resumed = gSystem.frameCounter - sFlyPrompt.lastFrame > 2;
    sFlyPrompt.lastFrame = gSystem.frameCounter;

    BOOL show = sFlyPrompt.flyAllowed && PokegearFly_DestinationAtCursor(mapApp) > 0;
    if (show == sFlyPrompt.shown && !resumed) {
        return;
    }
    FillWindowPixelBuffer(&sFlyPrompt.window, 0);
    if (show) {
        ReadMsgDataIntoString(mapApp->msgData, MSG_POKEGEAR_FLY_PROMPT, mapApp->flavorTextString);
        AddTextPrinterParameterizedWithColor(&sFlyPrompt.window, FONT_SYSTEM, mapApp->flavorTextString, 0, 4, TEXT_SPEED_NOTRANSFER, MAKE_TEXT_COLOR(1, 2, 0), NULL);
    }
    CopyWindowToVram(&sFlyPrompt.window);
    sFlyPrompt.shown = show;
}

// hook (overlay 101 021EB568): the map card's button input, vanilla plus A to fly
int LONG_CALL PokegearMap_HandleKeyInput(struct PokegearMapApp *mapApp)
{
    u32 newKeys = gSystem.newKeys;
    struct PokegearApp *pokegear = mapApp->pokegear;

    if ((newKeys & PAD_BUTTON_B) && !(mapApp->flags139 & 4)) {
        pokegear->cursorInAppSwitchZone = TRUE;
        PokegearCursorManager_SetCursorSpritesDrawState(pokegear->cursorManager, 0, TRUE);
        PokegearCursorManager_SetSpecIndexAndCursorPos(pokegear->cursorManager, 0, PokegearApp_AppIdToButtonIndex(pokegear));
        PokegearMap_HideMapCursor(mapApp);
        PlaySE(SEQ_SE_GS_GEARCANCEL);
        return -1;
    }

    // not while the cursor or a marking is moving (draggingMarking, unk_139_1, unk_139_2)
    if ((newKeys & PAD_BUTTON_A) && !(mapApp->flags139 & 7) && sFlyPrompt.created && sFlyPrompt.mapApp == mapApp && sFlyPrompt.flyAllowed) {
        int dest = PokegearFly_DestinationAtCursor(mapApp);
        if (dest > 0) {
            struct PokegearArgs *args = pokegear->args;
            args->setFlyDestination = TRUE;
            args->selectedFlyDest = dest;
            args->mapCursorX = mapApp->cursorX;
            args->mapCursorY = mapApp->cursorY - 2;
            PlaySE(SEQ_SE_GS_GEARDECIDE);
            return GEAR_RETURN_EXIT;
        }
    }

    int ret = PokegearMap_HandleKeyInput_Main(mapApp);
    if (ret == 7) {
        return ret;
    }
    PokegearMap_UpdateCursorMovement(mapApp);
    PokegearMap_UpdateSelection(mapApp);
    PokegearFly_UpdatePrompt(mapApp);
    return -1;
}

// hook (overlay 101 021E857C): the map card's windows are removed when it closes or opens the marking word screen
void LONG_CALL PokegearMap_RemoveWindows(struct PokegearMapApp *mapApp)
{
    if (sFlyPrompt.created && sFlyPrompt.mapApp == mapApp) {
        ClearWindowTilemapAndCopyToVram(&sFlyPrompt.window);
        RemoveWindow(&sFlyPrompt.window);
        sFlyPrompt.created = FALSE;
    }
    for (int i = 0; i < 8; i++) {
        ClearWindowTilemapAndCopyToVram(&mapApp->windows[i]);
        RemoveWindow(&mapApp->windows[i]);
    }
    RemoveWindow(&mapApp->windows[8]);
}

// hook (arm9 0203D550): back in the field after the Pokégear, flying if the map card picked a destination
BOOL LONG_CALL Task_StartMenu_HandleReturn_Pokegear(TaskManager *taskManager)
{
    FieldSystem *fsys = taskManager->fieldSystem;
    struct BagViewAppWork *startMenu = taskManager->env;
    struct PokegearArgs *args = startMenu->atexit_TaskEnv;

    u16 slot = args != NULL && args->setFlyDestination ? FieldHM_GetUser(fsys->savedata, MOVE_FLY) : 6;
    if (slot != 6) {
        void *fly = FlyTaskData_New(HEAP_ID_FIELD2, fsys, FieldHM_GetMon(fsys->savedata, slot), slot, args->selectedFlyDest,
            args->mapCursorX * 32 + 16, args->mapCursorY * 32 + 16);
        Heap_FreeExplicit(HEAP_ID_FIELD2, args);
        FieldSystem_LoadFieldOverlay(fsys);
        startMenu->atexit_TaskFunc = Task_FlyInField;
        startMenu->atexit_TaskEnv = fly;
        startMenu->state = START_MENU_STATE_RUN_TASK;
        return FALSE;
    }

    FieldSystem_LoadFieldOverlay(fsys);
    if (args != NULL) {
        Heap_FreeExplicit(HEAP_ID_FIELD2, args);
    }
    startMenu->state = START_MENU_STATE_RETURN;
    return FALSE;
}
