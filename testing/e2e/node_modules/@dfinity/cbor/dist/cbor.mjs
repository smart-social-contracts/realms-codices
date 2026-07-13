class w extends Error {
  constructor(e) {
    super(e), this.name = "DecodingError";
  }
}
const L = 55799, R = /* @__PURE__ */ Symbol("CBOR_STOP_CODE");
var u = /* @__PURE__ */ ((t) => (t[t.False = 20] = "False", t[t.True = 21] = "True", t[t.Null = 22] = "Null", t[t.Undefined = 23] = "Undefined", t[t.Break = 31] = "Break", t))(u || {}), c = /* @__PURE__ */ ((t) => (t[t.UnsignedInteger = 0] = "UnsignedInteger", t[t.NegativeInteger = 1] = "NegativeInteger", t[t.ByteString = 2] = "ByteString", t[t.TextString = 3] = "TextString", t[t.Array = 4] = "Array", t[t.Map = 5] = "Map", t[t.Tag = 6] = "Tag", t[t.Simple = 7] = "Simple", t))(c || {});
const Y = 23, G = 255, P = 65535, H = 4294967295, W = BigInt("0xffffffffffffffff");
var f = /* @__PURE__ */ ((t) => (t[t.Value = 23] = "Value", t[t.OneByte = 24] = "OneByte", t[t.TwoBytes = 25] = "TwoBytes", t[t.FourBytes = 26] = "FourBytes", t[t.EightBytes = 27] = "EightBytes", t[t.Indefinite = 31] = "Indefinite", t))(f || {});
const l = !1;
function K(t) {
  return t == null;
}
function Z(t, e) {
  const n = new Uint8Array(e);
  return n.set(t), n;
}
const q = new TextDecoder();
function J(t) {
  return (t & 224) >> 5;
}
function Q(t) {
  return t & 31;
}
let S = new Uint8Array(), U, d = 0;
function ut(t, e) {
  S = t, d = 0;
  const n = B(e);
  return e?.(n) ?? n;
}
function B(t) {
  const [e, n] = N();
  switch (e) {
    case c.UnsignedInteger:
      return h(n);
    case c.NegativeInteger:
      return M(n);
    case c.ByteString:
      return $(n);
    case c.TextString:
      return F(n);
    case c.Array:
      return p(n, t);
    case c.Map:
      return j(n, t);
    case c.Tag:
      return v(n, t);
    case c.Simple:
      return b(n);
  }
  throw new w(`Unsupported major type: ${e}`);
}
function N() {
  const t = S.at(d);
  if (K(t))
    throw new w("Provided CBOR data is empty");
  const e = J(t), n = Q(t);
  return d++, [e, n];
}
function p(t, e) {
  const n = h(t);
  if (n === 1 / 0) {
    const o = [];
    let i = B(e);
    for (; i !== R; )
      o.push(e?.(i) ?? i), i = B(e);
    return o;
  }
  const s = new Array(n);
  for (let o = 0; o < n; o++) {
    const i = B(e);
    s[o] = e?.(i) ?? i;
  }
  return s;
}
function b(t) {
  switch (t) {
    case u.False:
      return !1;
    case u.True:
      return !0;
    case u.Null:
      return null;
    case u.Undefined:
      return;
    case u.Break:
      return R;
  }
  throw new w(`Unrecognized simple type: ${t.toString(2)}`);
}
function j(t, e) {
  const n = h(t), s = {};
  if (n === 1 / 0) {
    let [o, i] = N();
    for (; o !== c.Simple && i !== u.Break; ) {
      const A = F(i), I = B(e);
      s[A] = e?.(I, A) ?? I, [o, i] = N();
    }
    return s;
  }
  for (let o = 0; o < n; o++) {
    const [i, A] = N();
    if (i !== c.TextString)
      throw new w("Map keys must be text strings");
    const I = F(A), D = B(e);
    s[I] = e?.(D, I) ?? D;
  }
  return s;
}
function h(t) {
  if (t <= f.Value)
    return t;
  switch (U = new DataView(S.buffer, S.byteOffset + d), t) {
    case f.OneByte:
      return d++, U.getUint8(0);
    case f.TwoBytes:
      return d += 2, U.getUint16(0, l);
    case f.FourBytes:
      return d += 4, U.getUint32(0, l);
    case f.EightBytes:
      return d += 8, U.getBigUint64(0, l);
    case f.Indefinite:
      return 1 / 0;
    default:
      throw new w(`Unsupported integer info: ${t.toString(2)}`);
  }
}
function M(t) {
  const e = h(t);
  return typeof e == "number" ? -1 - e : -1n - e;
}
function $(t) {
  const e = h(t);
  if (e > Number.MAX_SAFE_INTEGER)
    throw new w("Byte length is too large");
  const n = Number(e);
  return d += n, S.slice(d - n, d);
}
function F(t) {
  const e = $(t);
  return q.decode(e);
}
function v(t, e) {
  const n = h(t);
  if (n === L)
    return B(e);
  throw new w(`Unsupported tag: ${n}.`);
}
class x extends Error {
  constructor(e) {
    super(e), this.name = "SerializationError";
  }
}
const C = 2 * 1024, V = 100, tt = new TextEncoder();
function y(t) {
  return t << 5;
}
let a = new Uint8Array(C), g = new DataView(a.buffer), r = 0, O = [];
function dt(t, e) {
  r = 0;
  const n = e?.(t) ?? t;
  return _(n, e), a.slice(0, r);
}
function gt(t, e) {
  r = 0;
  const n = e?.(t) ?? t;
  return ft(L, n, e), a.slice(0, r);
}
function k(t) {
  let e = a.length * 2;
  for (; e < t; )
    e *= 2;
  a = Z(a, e), g = new DataView(a.buffer);
}
function _(t, e) {
  if (t === !1 || t === !0 || t === null || t === void 0) {
    rt(t);
    return;
  }
  if (typeof t == "number" || typeof t == "bigint") {
    ot(t);
    return;
  }
  if (typeof t == "string") {
    z(t);
    return;
  }
  if (t instanceof Uint8Array) {
    m(t);
    return;
  }
  if (t instanceof ArrayBuffer) {
    m(new Uint8Array(t));
    return;
  }
  if (Array.isArray(t)) {
    et(t, e);
    return;
  }
  if (typeof t == "object") {
    nt(t, e);
    return;
  }
  throw new x(`Unsupported type: ${typeof t}`);
}
function et(t, e) {
  E(c.Array, t.length), t.forEach((n, s) => {
    _(e?.(n, s.toString()) ?? n, e);
  });
}
function nt(t, e) {
  O = Object.entries(t), E(c.Map, O.length), O.forEach(([n, s]) => {
    z(n), _(e?.(s, n) ?? s, e);
  });
}
function E(t, e) {
  if (r > a.length - V && k(r + V), e <= Y) {
    g.setUint8(
      r++,
      y(t) | Number(e)
    );
    return;
  }
  if (e <= G) {
    g.setUint8(
      r++,
      y(t) | f.OneByte
    ), g.setUint8(r, Number(e)), r += 1;
    return;
  }
  if (e <= P) {
    g.setUint8(
      r++,
      y(t) | f.TwoBytes
    ), g.setUint16(r, Number(e), l), r += 2;
    return;
  }
  if (e <= H) {
    g.setUint8(
      r++,
      y(t) | f.FourBytes
    ), g.setUint32(r, Number(e), l), r += 4;
    return;
  }
  if (e <= W) {
    g.setUint8(
      r++,
      y(t) | f.EightBytes
    ), g.setBigUint64(r, BigInt(e), l), r += 8;
    return;
  }
  throw new x(`Value too large to encode: ${e}`);
}
function rt(t) {
  E(c.Simple, ct(t));
}
function ct(t) {
  if (t === !1)
    return u.False;
  if (t === !0)
    return u.True;
  if (t === null)
    return u.Null;
  if (t === void 0)
    return u.Undefined;
  throw new x(`Unrecognized simple value: ${t.toString()}`);
}
function T(t, e) {
  E(t, e.length), r > a.length - e.length && k(r + e.length), a.set(e, r), r += e.length;
}
function X(t, e) {
  E(t, e);
}
function it(t) {
  X(c.UnsignedInteger, t);
}
function st(t) {
  X(
    c.NegativeInteger,
    typeof t == "bigint" ? -1n - t : -1 - t
  );
}
function ot(t) {
  t >= 0 ? it(t) : st(t);
}
function z(t) {
  T(c.TextString, tt.encode(t));
}
function m(t) {
  T(c.ByteString, t);
}
function ft(t, e, n) {
  E(c.Tag, t), _(e, n);
}
export {
  w as DecodingError,
  x as EncodingError,
  ut as decode,
  dt as encode,
  gt as encodeWithSelfDescribedTag
};
//# sourceMappingURL=cbor.mjs.map
