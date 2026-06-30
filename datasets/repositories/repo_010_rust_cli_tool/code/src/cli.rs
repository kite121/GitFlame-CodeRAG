pub struct Options {
    pub path: String,
    pub recursive: bool,
    pub json: bool,
}

// BUG: unknown flags are silently ignored instead of reported.
pub fn parse(args: &[String]) -> Result<Options, String> {
    let mut path = String::from(".");
    let mut recursive = false;
    let mut json = false;
    for arg in args {
        match arg.as_str() {
            "-r" | "--recursive" => recursive = true,
            "--json" => json = true,
            other if !other.starts_with('-') => path = other.to_string(),
            _ => {}
        }
    }
    Ok(Options { path, recursive, json })
}
