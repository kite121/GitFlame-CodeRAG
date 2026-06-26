mod cli;
mod counter;
mod report;

use std::process::exit;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let options = match cli::parse(&args) {
        Ok(opts) => opts,
        Err(message) => {
            eprintln!("error: {message}");
            exit(2);
        }
    };
    let stats = counter::count_path(&options.path, options.recursive);
    println!("{}", report::render(&stats, options.json));
}
