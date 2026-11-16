#include "../../include/types.h"
#include "../../include/message.h"
#include "../../include/pokemon.h"
#include "../../include/constants/file.h"
#include "../../include/constants/item.h"
#include "../../include/constants/moves.h"

// Encore: Poké Mart TM move names.
//
// Replaces ov31_0225E4BC (pret/pokeheartgold asm/overlay_31.s), which the mart's bottom screen calls to buffer the
// item being bought into its MessageFormat. It still buffers the item name, and for a TM, HM or TR it also buffers
// the move name and a space into slots the mart's messages don't otherwise use. Message 12 of data/text/435.txt is
// "{item}{STRVAR slot 7}{STRVAR slot 6}?{STRVAR slot 5}\nHow many would you like?". A TM reads "TM024 Thunderbolt?",
// because " Certainly." (message 50) doesn't fit after the longest names, e.g. "TM136 ElectricTerrain". Any other item
// gets " Certainly." in slot 5 and reads as vanilla. Item names in data/text/222.txt are unchanged, so the bag and the
// shop list keep "TM024".

#define MART_TYPE_NORMAL 0
#define MART_TYPE_DECORATION 1
#define MART_TYPE_POKEATHLON_DAILY 3
#define MART_TYPE_DATA_CARDS 4

#define MSG_MOVE_NAMES 750
#define MSG_MART 435
#define MSG_MART_CERTAINLY 50
#define CHAR_SPACE 0x01DE
#define CHAR_EOS 0xFFFF

// MessageFormat slots the mart's messages don't use (it has 8; they use 0 and 1)
#define MART_SLOT_CERTAINLY 5
#define MART_SLOT_MOVE 6
#define MART_SLOT_SPACE 7

void LONG_CALL BufferDecorationName(MessageFormat *msgFmt, u32 fieldno, u32 decorationId);

static void Mart_BufferMachineMoveName(MessageFormat *msgFmt, u16 itemId)
{
    u16 text[24];
    u16 move = MOVE_NONE;

    if (IS_ITEM_TM(itemId) || IS_ITEM_HM(itemId) || IS_ITEM_TR(itemId)) {
        move = ItemToMachineMove(itemId);
    }

    text[0] = CHAR_EOS;
    if (move != MOVE_NONE) {
        MsgData *msgData = NewMsgDataFromNarc(MSGDATA_LOAD_LAZY, ARC_MSG_DATA, MSG_MOVE_NAMES, msgFmt->heapId);
        if (msgData != NULL) {
            ReadMsgDataIntoU16Array(msgData, move, text);
            DestroyMsgData(msgData);
            text[NELEMS(text) - 1] = CHAR_EOS;
            CopyU16ArrayToString(msgFmt->buffer, text);
            SetStringAsPlaceholder(msgFmt, MART_SLOT_MOVE, msgFmt->buffer, NULL);
            text[0] = CHAR_SPACE;
            text[1] = CHAR_EOS;
            CopyU16ArrayToString(msgFmt->buffer, text);
            SetStringAsPlaceholder(msgFmt, MART_SLOT_SPACE, msgFmt->buffer, NULL);
            text[0] = CHAR_EOS;
            CopyU16ArrayToString(msgFmt->buffer, text);
            SetStringAsPlaceholder(msgFmt, MART_SLOT_CERTAINLY, msgFmt->buffer, NULL);
            return;
        }
    }

    // not a machine: no move name, and " Certainly." as in vanilla
    CopyU16ArrayToString(msgFmt->buffer, text);
    SetStringAsPlaceholder(msgFmt, MART_SLOT_MOVE, msgFmt->buffer, NULL);
    SetStringAsPlaceholder(msgFmt, MART_SLOT_SPACE, msgFmt->buffer, NULL);
    MsgData *msgData = NewMsgDataFromNarc(MSGDATA_LOAD_LAZY, ARC_MSG_DATA, MSG_MART, msgFmt->heapId);
    if (msgData != NULL) {
        ReadMsgDataIntoU16Array(msgData, MSG_MART_CERTAINLY, text);
        DestroyMsgData(msgData);
        text[NELEMS(text) - 1] = CHAR_EOS;
        CopyU16ArrayToString(msgFmt->buffer, text);
    }
    SetStringAsPlaceholder(msgFmt, MART_SLOT_CERTAINLY, msgFmt->buffer, NULL);
}

void LONG_CALL Mart_BufferPurchaseItemName(u32 martType, MessageFormat *msgFmt, u32 itemId, u32 fieldno)
{
    switch (martType) {
    case MART_TYPE_NORMAL:
    case MART_TYPE_POKEATHLON_DAILY:
    case MART_TYPE_DATA_CARDS:
        BufferItemName(msgFmt, fieldno, itemId);
        Mart_BufferMachineMoveName(msgFmt, itemId);
        break;
    case MART_TYPE_DECORATION:
        BufferDecorationName(msgFmt, fieldno, itemId);
        Mart_BufferMachineMoveName(msgFmt, ITEM_NONE); // a decoration ID isn't an item, so never a TM
        break;
    }
}
