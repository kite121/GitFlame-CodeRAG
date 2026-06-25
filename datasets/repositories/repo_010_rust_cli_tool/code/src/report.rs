use crate::counter::Stats;

pub fn render(stats: &Stats, json: bool) -> String {
    if json {
        // NOTE: hand-rolled JSON does not escape strings; fine for numbers only.
        format!(
            "{{\"files\":{},\"lines\":{},\"bytes\":{}}}",
            stats.files, stats.lines, stats.bytes
        )
    } else {
        format!(
            "files: {}\nlines: {}\nbytes: {}",
            stats.files, stats.lines, stats.bytes
        )
    }
}
