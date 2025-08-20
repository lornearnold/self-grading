# Student self-graded homework

A secure, scalable approach to student-graded homework for self-reflection.

Author: Dr. Matthew Ford (mattford@uw.edu) ([Website](https://dashdotrobot.com/))

Use this script to compare student self-graded scores to instructor scores and enter final grades into the Canvas gradebook.

## Instructions

### Set up a new course
1. Run this script with no arguments. It will prompt you to create a default configuration file.
2. Obtain a Canvas API key and enter it in the `api_key` field.
3. Replace `canvas_url` with your institution's Canvas web address.
4. Change the other options if desired.

### Create an assignment
1. Assign homework on Canvas: Create a Canvas assignment with the suffix `submission_suffix`, e.g. "Homework 3 - submit your work". This is the assignment students will use to submit their homework and for you to grade the "check problem". Move this assignment to an Assignment Group worth 0% of the final grade, or select the option "Do not count this assignment towards the final grade" in Canvas.
2. Create a Canvas quiz (Classic Quizzes) with the suffix `score_suffix`, e.g. "Homework 3 - grade your work". Move this assignment to an Assignment Group worth 0% of the final grade, or select the option "Do not count this assignment towards the final grade" in Canvas.
3. Add a text-only question with links to the homework solutions and grading rubrics.
4. Add a Numerical Answer question corresponding to each homework problem. Name each problem "Problem X" where "X" is an integer. Set the "answer" to -1, and set the point value to the number of points you would like the question to be worth. Students should enter their score for each problem here. __Remind students that the "grade" that Canvas calculates for their quiz is irrelevant.__
5. You may add other questions to the quiz, such as a file-upload question for students to submit their filled-out rubric, or an academic integrity attestation.
6. Set the quiz "Available from" date to just shortly after the homework is due. This will automatically give students access to the solutions after the homework submission deadline.

### Grade an assignment
After students have submitted their grades,

1. Choose one problem from the assignment to grade yourself. Enter your score for the "check problem" on the submission assignment (e.g. "Homework X - submit your work"). If you use an external grading tool, like Gradescope, just sync your grades back to the submission assignment in Canvas.
2. __Fetch scores__: Run this script with the `-f` or `--fetch` option. You can optionally provide the assignment ID and check problem name as command line arguments, otherwise the script will prompt you for a selection.
3. __Check scores__: Open the newly-created file "Homework X_scores.csv". The script creates two columns for each problem with the suffixes "_s" for the student-entered score, and "_i" for your score (blank for all problems except the check problem). Look for concerning discrepancies. If a student score differs by a small amount, you can leave it alone; the script will replace their score with yours for the check problem when computing the final grade. If a student score differs by a large amount, you may consider reviewing the rest of the student's submission. You can override student scores for any other problem by entering a score into the "_i" column.
4. Set the `checked` column to TRUE when you have reviewed a student's grade and either found it satisfactory, or made appropriate score adjustments.
4. Create a Canvas assignment with the suffix `final_suffix`, e.g. "Homework 3 - final grade". Optionally, the script will prompt you to create one if it doesn't exist. Make sure you publish the assignment before proceeding. Make sure this assignment does count towards the student's grade!
5. __Upload scores__: Run this script again with the `-u` or `--upload` option. This will upload scores to Canvas for all students marked Checked.

### Updating scores
Depending on your course policy, you may allow students to submit late work, or resubmit assignments. Use this script to update and re-sync scores.

- If scores have previously been fetched, running the script with the `-f` option will check whether there is a new assignment submission and prompt you to erase any instructor scores. You can ignore the prompts and reset all instructor scores with the `-o` or `--overwrite` option.
- If a new student grade submission is found, the instructor scores will not be cleared, but the `checked` field will be set to False so you can double check the students' newly submitted scores.

## Example usage

### Fetch scores for assignment ID 12345 with a given check problem

`python update_scores.py -a 12345 -p "Problem 4" -f`

### Upload scores. Prompt for assignment name.

`python update_scores.py -u`