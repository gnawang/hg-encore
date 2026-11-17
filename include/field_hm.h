#ifndef FIELD_HM_H
#define FIELD_HM_H

#include "item.h"
#include "types.h"

// Encore: party slot that stands for the "helpful Pokémon" using a field HM nobody in the party knows.
// The vanilla scripts use 6 for "no Pokémon", so the rental uses 7. Also defined in asm/include/scriptmacros.inc.
#define HM_RENTAL_SLOT 7

u16 FieldHM_GetUser(void *saveData, u16 move);

#endif // FIELD_HM_H
