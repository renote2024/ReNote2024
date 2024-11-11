from diskcache import Index
import pip
import pandas as pd
import os


def main(cache_path, csv):
    nb_cache = Index(cache_path)
    results = [v for k, v in nb_cache.items()]
    df = pd.DataFrame(results)
    df.to_csv(csv)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Read all .ipynb files in a directory.')
    parser.add_argument('--results_cache_path', type=str, required=True, help='Path to the results cache [DiskCache]')
    parser.add_argument('--csv', type=str, default=True, help='csv file path to save the results')

    args = parser.parse_args()
    main(results_cache_path=args.results_cache_path, csv= args.csv)
    print(f"Results saved to {args.csv}")
