#include "../../include/constants/species.h"
#include "../../include/npc_trade.h"
#include "../../include/pokemon.h"
#include "../../include/save.h"
#include "../../include/types.h"

void __attribute__((section(".init"))) CreateTradeMon_Internal(struct PartyPokemon *mon, struct NPCTrade *trade_dat, u32 level, u32 tradeno, u32 mapno, u32 met_level_strat, u32 heapId)
{
    String *name;
    u8 nickname_flag;
    u32 mapsec;
    int heapId_2;

    // Encore: the trade Pokemon carries the player's visible Trainer ID in the low half of its OT ID. The Name Rater
    // (ScrCmd_PartyMonIsMine) compares only that half, so it can rename the Pokemon. Battles compare the full ID, OT name
    // and OT gender, so it still counts as traded: boosted EXP and the badge obedience check. The secret half is chosen so
    // the Pokemon can't become shiny, as in vanilla. Kenya and Shuckie keep their vanilla ID, because the mail delivery and
    // Kirk's request to return Shuckie look for it.
    u32 otId = (u32)trade_dat->otId;
    if (tradeno != NPC_TRADE_KENYA_SPEAROW && tradeno != NPC_TRADE_SHUCKIE_SHUCKLE)
    {
        u32 visibleId = PlayerProfile_GetTrainerID_VisibleHalf(Sav2_PlayerData_GetProfileAddr(SaveBlock2_get()));
        u32 pid = (u32)trade_dat->pid;
        u32 secretId = (visibleId ^ (pid >> 16) ^ (pid & 0xFFFF) ^ 0x8000) & 0xFFFF;
        otId = (secretId << 16) | visibleId;
    }

    PokeParaSet(mon, trade_dat->give_species, level, 32, TRUE, trade_dat->pid, OT_ID_PRESET, otId);

    heapId_2 = (int)heapId;
    name = _GetNpcTradeName(heapId_2, tradeno);
    SetMonData(mon, MON_DATA_NICKNAME_3 /*MON_DATA_NICKNAME_STRING = 119*/, name);
    String_Delete(name);

    nickname_flag = TRUE;
    SetMonData(mon, MON_DATA_HAS_NICKNAME, &nickname_flag);

    SetMonData(mon, MON_DATA_HP_IV, &trade_dat->hpIv);
    SetMonData(mon, MON_DATA_ATK_IV, &trade_dat->atkIv);
    SetMonData(mon, MON_DATA_DEF_IV, &trade_dat->defIv);
    SetMonData(mon, MON_DATA_SPEED_IV, &trade_dat->speedIv);
    SetMonData(mon, MON_DATA_SPATK_IV, &trade_dat->spAtkIv);
    SetMonData(mon, MON_DATA_SPDEF_IV, &trade_dat->spDefIv);

    SetMonData(mon, MON_DATA_COOL, &trade_dat->cool);
    SetMonData(mon, MON_DATA_BEAUTY, &trade_dat->beauty);
    SetMonData(mon, MON_DATA_CUTE, &trade_dat->cute);
    SetMonData(mon, MON_DATA_SMART, &trade_dat->smart);
    SetMonData(mon, MON_DATA_TOUGH, &trade_dat->tough);

    SetMonData(mon, MON_DATA_HELD_ITEM, &trade_dat->heldItem);

    name = _GetNpcTradeName(heapId_2, NPC_TRADE_OT_NUM(tradeno));
    SetMonData(mon, MON_DATA_OT_NAME_2, name);
    String_Delete(name);

    SetMonData(mon, MON_DATA_MET_GENDER, &trade_dat->gender);
    SetMonData(mon, MON_DATA_GAME_LANGUAGE, &trade_dat->language);

    mapsec = MapHeader_GetMapSec(mapno);
    MonSetTrainerMemo(mon, NULL, met_level_strat, mapsec, heapId);

    RecalcPartyPokemonStats(mon); // CalcMonLevelAndStats(mon);
    // GF_ASSERT(!MonIsShiny(mon));
}
