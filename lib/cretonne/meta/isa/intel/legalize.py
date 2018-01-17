"""
Custom legalization patterns for Intel.
"""
from __future__ import absolute_import
from cdsl.ast import Var
from cdsl.xform import Rtl, XFormGroup
from base.immediates import imm64, intcc, floatcc
from base.types import i32, i64
from base import legalize as shared
from base import instructions as insts
from . import instructions as x86
from .defs import ISA

intel_expand = XFormGroup(
        'intel_expand',
        """
        Legalize instructions by expansion.

        Use Intel-specific instructions if needed.
        """,
        isa=ISA, chain=shared.expand)

a = Var('a')
dead = Var('dead')
x = Var('x')
xhi = Var('xhi')
y = Var('y')
a1 = Var('a1')
a2 = Var('a2')

#
# Division and remainder.
#
intel_expand.legalize(
        a << insts.udiv(x, y),
        Rtl(
            xhi << insts.iconst(imm64(0)),
            (a, dead) << x86.udivmodx(x, xhi, y)
        ))

intel_expand.legalize(
        a << insts.urem(x, y),
        Rtl(
            xhi << insts.iconst(imm64(0)),
            (dead, a) << x86.udivmodx(x, xhi, y)
        ))

for ty in [i32, i64]:
    intel_expand.legalize(
            a << insts.sdiv.bind(ty)(x, y),
            Rtl(
                xhi << insts.sshr_imm(x, imm64(ty.lane_bits() - 1)),
                (a, dead) << x86.sdivmodx(x, xhi, y)
            ))

# The srem expansion requires custom code because srem INT_MIN, -1 is not
# allowed to trap.
intel_expand.custom_legalize(insts.srem, 'expand_srem')

# Floating point condition codes.
#
# The 8 condition codes in `supported_floatccs` are directly supported by a
# `ucomiss` or `ucomisd` instruction. The remaining codes need legalization
# patterns.

# Equality needs an explicit `ord` test which checks the parity bit.
intel_expand.legalize(
        a << insts.fcmp(floatcc.eq, x, y),
        Rtl(
            a1 << insts.fcmp(floatcc.ord, x, y),
            a2 << insts.fcmp(floatcc.ueq, x, y),
            a << insts.band(a1, a2)
        ))
intel_expand.legalize(
        a << insts.fcmp(floatcc.ne, x, y),
        Rtl(
            a1 << insts.fcmp(floatcc.uno, x, y),
            a2 << insts.fcmp(floatcc.one, x, y),
            a << insts.bor(a1, a2)
        ))

# Inequalities that need to be reversed.
for cc,               rev_cc in [
        (floatcc.lt,  floatcc.gt),
        (floatcc.le,  floatcc.ge),
        (floatcc.ugt, floatcc.ult),
        (floatcc.uge, floatcc.ule)]:
    intel_expand.legalize(
            a << insts.fcmp(cc, x, y),
            Rtl(
                a << insts.fcmp(rev_cc, y, x)
            ))

# We need to modify the CFG for min/max legalization.
intel_expand.custom_legalize(insts.fmin, 'expand_minmax')
intel_expand.custom_legalize(insts.fmax, 'expand_minmax')

# Conversions from unsigned need special handling.
intel_expand.custom_legalize(insts.fcvt_from_uint, 'expand_fcvt_from_uint')
# Conversions from float to int can trap.
intel_expand.custom_legalize(insts.fcvt_to_sint, 'expand_fcvt_to_sint')
intel_expand.custom_legalize(insts.fcvt_to_uint, 'expand_fcvt_to_uint')

# Count leading and trailing zeroes, for baseline x86_64
c_minus_one = Var('c_minus_one')
c_thirty_one = Var('c_thirty_one')
c_thirty_two = Var('c_thirty_two')
c_sixty_three = Var('c_sixty_three')
c_sixty_four = Var('c_sixty_four')
index1 = Var('index1')
r2flags = Var('r2flags')
index2 = Var('index2')

intel_expand.legalize(
    a << insts.clz.i64(x),
    Rtl(
        c_minus_one << insts.iconst(imm64(-1)),
        c_sixty_three << insts.iconst(imm64(63)),
        (index1, r2flags) << x86.bsr(x),
        index2 << insts.selectif(intcc.eq, r2flags, c_minus_one, index1),
        a << insts.isub(c_sixty_three, index2),
    ))

intel_expand.legalize(
    a << insts.clz.i32(x),
    Rtl(
        c_minus_one << insts.iconst(imm64(-1)),
        c_thirty_one << insts.iconst(imm64(31)),
        (index1, r2flags) << x86.bsr(x),
        index2 << insts.selectif(intcc.eq, r2flags, c_minus_one, index1),
        a << insts.isub(c_thirty_one, index2),
    ))

intel_expand.legalize(
    a << insts.ctz.i64(x),
    Rtl(
        c_sixty_four << insts.iconst(imm64(64)),
        (index1, r2flags) << x86.bsf(x),
        a << insts.selectif(intcc.eq, r2flags, c_sixty_four, index1),
    ))

intel_expand.legalize(
    a << insts.ctz.i32(x),
    Rtl(
        c_thirty_two << insts.iconst(imm64(32)),
        (index1, r2flags) << x86.bsf(x),
        a << insts.selectif(intcc.eq, r2flags, c_thirty_two, index1),
    ))


# Population count for baseline x86_64
qv1 = Var('qv1')
qv3 = Var('qv3')
qv4 = Var('qv4')
qv5 = Var('qv5')
qv6 = Var('qv6')
qv7 = Var('qv7')
qv8 = Var('qv8')
qv9 = Var('qv9')
qv10 = Var('qv10')
qv11 = Var('qv11')
qv12 = Var('qv12')
qv13 = Var('qv13')
qv14 = Var('qv14')
qv15 = Var('qv15')
qv16 = Var('qv16')
qc77 = Var('qc77')
qc0F = Var('qc0F')
qc01 = Var('qc01')
intel_expand.legalize(
    qv16 << insts.popcnt.i64(qv1),
    Rtl(
        qv3 << insts.ushr_imm(qv1, imm64(1)),
        qc77 << insts.iconst(imm64(0x7777777777777777)),
        qv4 << insts.band(qv3, qc77),
        qv5 << insts.isub(qv1, qv4),
        qv6 << insts.ushr_imm(qv4, imm64(1)),
        qv7 << insts.band(qv6, qc77),
        qv8 << insts.isub(qv5, qv7),
        qv9 << insts.ushr_imm(qv7, imm64(1)),
        qv10 << insts.band(qv9, qc77),
        qv11 << insts.isub(qv8, qv10),
        qv12 << insts.ushr_imm(qv11, imm64(4)),
        qv13 << insts.iadd(qv11, qv12),
        qc0F << insts.iconst(imm64(0x0F0F0F0F0F0F0F0F)),
        qv14 << insts.band(qv13, qc0F),
        qc01 << insts.iconst(imm64(0x0101010101010101)),
        qv15 << insts.imul(qv14, qc01),
        qv16 << insts.ushr_imm(qv15, imm64(56))
    ))

lv1 = Var('lv1')
lv3 = Var('lv3')
lv4 = Var('lv4')
lv5 = Var('lv5')
lv6 = Var('lv6')
lv7 = Var('lv7')
lv8 = Var('lv8')
lv9 = Var('lv9')
lv10 = Var('lv10')
lv11 = Var('lv11')
lv12 = Var('lv12')
lv13 = Var('lv13')
lv14 = Var('lv14')
lv15 = Var('lv15')
lv16 = Var('lv16')
lc77 = Var('lc77')
lc0F = Var('lc0F')
lc01 = Var('lc01')
intel_expand.legalize(
    lv16 << insts.popcnt.i32(lv1),
    Rtl(
        lv3 << insts.ushr_imm(lv1, imm64(1)),
        lc77 << insts.iconst(imm64(0x77777777)),
        lv4 << insts.band(lv3, lc77),
        lv5 << insts.isub(lv1, lv4),
        lv6 << insts.ushr_imm(lv4, imm64(1)),
        lv7 << insts.band(lv6, lc77),
        lv8 << insts.isub(lv5, lv7),
        lv9 << insts.ushr_imm(lv7, imm64(1)),
        lv10 << insts.band(lv9, lc77),
        lv11 << insts.isub(lv8, lv10),
        lv12 << insts.ushr_imm(lv11, imm64(4)),
        lv13 << insts.iadd(lv11, lv12),
        lc0F << insts.iconst(imm64(0x0F0F0F0F)),
        lv14 << insts.band(lv13, lc0F),
        lc01 << insts.iconst(imm64(0x01010101)),
        lv15 << insts.imul(lv14, lc01),
        lv16 << insts.ushr_imm(lv15, imm64(24))
    ))
