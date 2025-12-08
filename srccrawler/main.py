from scrapy.cmdline import execute


def main():
    execute(['scrapy', 'crawl', 'genshin_impact_spider'])


if __name__ == '__main__':
    main()
