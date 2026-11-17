#include "../include/config.h"
#include "../include/constants/file.h"
#include "../include/pokemon.h"
#include "../include/repel.h"
#include "../include/roamer.h"
#include "../include/save.h"
#include "../include/script.h"
#include "../include/types.h"
#include "../include/field_hm.h"

#define SCRIPT_NEW_CMD_REPEL_USE 0
#define SCRIPT_NEW_CMD_SET_LAST_MON_FATEFUL 1
#define SCRIPT_NEW_CMD_GET_HM_USER          2

#define SCRIPT_NEW_CMD_MAX 256

BOOL Script_RunNewCmd(SCRIPTCONTEXT *ctx)
{
    u8 sw = ScriptReadByte(ctx);
    u16 UNUSED arg0 = ScriptReadHalfword(ctx);

    switch (sw) {
    case SCRIPT_NEW_CMD_REPEL_USE:;
#ifdef IMPLEMENT_REUSABLE_REPELS
        u16 most_recent_repel = Repel_GetMostRecent();
        SetScriptVar(arg0, most_recent_repel);
        Repel_Use(most_recent_repel, HEAPID_MAIN_HEAP);
#endif
        break;

    // vanilla events and obedience need a fateful encounter, which only Mystery Gift normally gives
    case SCRIPT_NEW_CMD_SET_LAST_MON_FATEFUL:;
        struct Party *party = SaveData_GetPlayerPartyPtr(ctx->fsys->savedata);
        u8 fateful = TRUE;
        SetMonData(Party_GetMonByIndex(party, party->count - 1), MON_DATA_FATEFUL_ENCOUNTER, &fateful);
        break;

    // Encore: party slot of the Pokémon that uses a field HM, HM_RENTAL_SLOT for a helpful Pokémon, or 6 for none
    case SCRIPT_NEW_CMD_GET_HM_USER:;
        u16 move = ScriptReadHalfword(ctx);
        *GetVarPointer(ctx->fsys, arg0) = FieldHM_GetUser(ctx->fsys->savedata, move);
        break;

    default:
        break;
    }

    return FALSE;
}

#ifdef EXPAND_ROAMERS
BOOL LONG_CALL ScrCmd_CreateRoamer(SCRIPTCONTEXT *ctx)
{
    u8 roamerNo = ScriptReadByte(ctx);
    Save_CreateRoamerByID(ctx->fsys->savedata, roamerNo);
    return FALSE;
}
#endif // EXPAND_ROAMERS
