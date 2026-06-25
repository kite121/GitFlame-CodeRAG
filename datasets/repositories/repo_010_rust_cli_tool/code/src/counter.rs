use std::fs;
use std::path::Path;

#[derive(Default)]
pub struct Stats {
    pub files: usize,
    pub lines: usize,
    pub bytes: usize,
}

pub fn count_path(path: &str, recursive: bool) -> Stats {
    let mut stats = Stats::default();
    visit(Path::new(path), recursive, &mut stats);
    stats
}

fn visit(path: &Path, recursive: bool, stats: &mut Stats) {
    if path.is_file() {
        if let Ok(content) = fs::read_to_string(path) {
            stats.files += 1;
            stats.lines += content.lines().count();
            stats.bytes += content.len();
        }
    } else if path.is_dir() && recursive {
        if let Ok(entries) = fs::read_dir(path) {
            for entry in entries.flatten() {
                visit(&entry.path(), recursive, stats);
            }
        }
    }
}
