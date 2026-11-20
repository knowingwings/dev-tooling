use std::sync::Mutex;
use std::time::{Duration, SystemTime};

static mut COUNTER: u32 = 0;

fn duty(x: f32) -> u16 {
    x as u16
}

#[allow(clippy::float_cmp)]
fn same(a: f32, b: f32) -> bool {
    a == b
}

#[expect(clippy::float_cmp, reason = "exact sentinel value written by the firmware")]
fn is_sentinel(a: f32) -> bool {
    a == -1.0
}

fn main() {
    let m = Mutex::new(1);
    let v = m.lock().unwrap();
    std::thread::sleep(Duration::from_millis(10));
    let _t = SystemTime::now();
    println!("{} {} {} {}", duty(0.5), same(1.0, 1.0), is_sentinel(0.0), *v);
    unsafe { COUNTER += 1; }
}
