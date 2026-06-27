# litmus7_project

## The Problem
The immense volume of unstructured product reviews makes manual analysis inefficient for businesses seeking actionable insights.

## The Solution
- Instead of prompting an entire list of reviews, we use a Divide and conquer
approach.
- Eg: 1000 reviews chunking the reviews into smaller chunks like 100 reviews
Then, take the Business-related context from the reviews.
- These chunks (100/1000 reviews) are sent to small sub parallel models of a
root model.
- Then root model Aggregate the sub models and filter out the data for best result
and quality
