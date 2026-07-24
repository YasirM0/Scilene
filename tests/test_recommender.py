from services.recommender import JournalRecommender


def main():
    recommender = JournalRecommender()

    recommendations = recommender.recommend(
        title="Digital Inclusion",
        keywords=[
            "education",
            "digital",
            "sociology",
        ]
    )

    print(f"Found {len(recommendations)} recommendations\n")

    for recommendation in recommendations[:3]:

        print("=" * 80)
        print(f"Journal : {recommendation['title']}")
        print(f"Publisher : {recommendation['publisher']}")
        print(f"Country : {recommendation['country']}")
        print(f"Score : {recommendation['score']:.1f}  (confidence: {recommendation['confidence']})")
        print(f"Why: {recommendation['explanation']}")
        print()


if __name__ == "__main__":
    main()