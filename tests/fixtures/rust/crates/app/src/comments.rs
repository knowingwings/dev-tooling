//! Module docs: allowed.

/// Public API docs: allowed.
pub fn first<'a>(xs: &'a [u8]) -> Option<&'a u8> {
    // just grab the first one for now
    let s = r#"// not a comment"#;
    let _ = s;
    'outer: loop {
        break 'outer;
    }
    xs.first()
}

pub fn raw(p: *const u8) -> u8 {
    // SAFETY: caller guarantees p is valid for one byte
    unsafe { *p }
}

/* nested /* block */ comment */
pub const C: char = '"';
