#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Update Canvas grades for a student-graded assignment."""

import json
from pprint import pprint
import os
import pandas as pd
from numpy import argmax
from itertools import chain
from canvasapi import Canvas
from argparse import ArgumentParser

def calc_final_scores(df):
    """Calculate final scores for each student, including instructor check scores."""

    scores_i = df.loc[:, df.columns.str.endswith("_i")]
    scores_i.columns = scores_i.columns.str.removesuffix("_i")

    scores_s = df.loc[:, df.columns.str.endswith("_s")]
    scores_s.columns = scores_s.columns.str.removesuffix("_s")

    df["student_score"] = scores_s.sum(axis=1)
    df["final_score"] = scores_i.fillna(scores_s).sum(axis=1)

    return df

def main():
    parser = ArgumentParser(description="Update Canvas grades for a student-graded assignment.")
    parser.add_argument("-c", "--course_id", help="Canvas course ID", type=int)
    parser.add_argument("-a", "--assignment_id", help="Canvas assignment ID", type=int)
    parser.add_argument("-p", "--check_problem", help="Check Problem name (e.g. 'Problem 3')")
    parser.add_argument("-f", "--fetch", help="Fetch scores from Canvas", action="store_true")
    parser.add_argument("-u", "--upload", help="Upload scores to Canvas", action="store_true")
    parser.add_argument("-o", "--overwrite", help="Overwrite existing instructor scores", action="store_true")
    parser.add_argument("-v", "--verbose", help="Enable verbose output", action="store_true")
    args = parser.parse_args()

    # Check if config.txt exists, otherwise exit with error
    try:
        with open("config.txt", "r") as f:
            # parse JSON configuration file
            config = json.load(f)
            api_key = config["api_key"]
            canvas_url = config["canvas_url"]
    except FileNotFoundError:
        # Prompt the user for the API key and Canvas URL and create config.txt
        create_config = input("config.txt not found. Create one? (y/n)")
        if create_config.strip().lower() == 'y':

            # Create empty configuration file
            with open("config.txt", "w") as f:
                json.dump({
                    "api_key": "ENTER YOUR API KEY",
                    "canvas_url": "https://canvas.myinstitution.edu",
                    "course_id": 123,
                    "submission_suffix": "submit your work",
                    "score_suffix": "grade your work",
                    "final_suffix": "final grade",
                    "problem_prefix": "Problem"}, f, indent=4)
                print("config.txt created. Open it and fill in the required fields.")
                return
        else:
            print("Exiting.")
            return
    except Exception as e:
        print(f"Error reading config.txt: {e}")
        return

    # Create Canvas connection
    canvas = Canvas(canvas_url, api_key)

    # Select Canvas course
    if args.course_id:
        print("Course ID from command line arg")
        course = canvas.get_course(args.course_id)
    elif "course_id" in config:
        print("Course ID from config")
        course = canvas.get_course(config["course_id"])
    else:
        # Search for course by name
        course_name = input("Enter part of the Canvas course name: ")

        if course_name == "":
            # If no course name is provided, list all courses
            matching_courses = [c for c in canvas.get_courses()]
        else:
            # Filter courses by name
            matching_courses = [c for c in canvas.get_courses() if course_name.lower() in c.name.lower()]
        
        if len(matching_courses) > 1:  # Multiple courses found
            for i, c in enumerate(matching_courses):
                print(f"[{i + 1}]: {c.name}")
            
            course_num = int(input("Choose a course by number:")) - 1
            course = matching_courses[course_num]
        elif len(matching_courses) == 1:  # Only one course found
            course = matching_courses[0]
        else:
            print("No matching courses found.")
            return

    print(f"Selected course: {course.name}")

    # Prompt for assignment ID if not provided
    if not args.assignment_id:
        # Search for assignment by name
        assignment_name = input("Enter part of the Canvas assignment name: ")

        if assignment_name == "":
            # If no assignment name is provided, list all assignments
            matching_assignments = [a for a in course.get_assignments()]
        else:
            matching_assignments = [a for a in course.get_assignments() if assignment_name.lower() in a.name.lower()]
        

        if len(matching_assignments) > 1:
            for i, a in enumerate(matching_assignments):
                print(f"[{i + 1}]: {a.name}")

            assignment_num = int(input("Choose an assignment by number:")) - 1
            assignment = matching_assignments[assignment_num]
        elif len(matching_assignments) == 1:  # Only one assignment found
            assignment = matching_assignments[0]
        else:
            print("No matching assignments found.")
            return
    else:
        assignment = course.get_assignment(args.assignment_id)

    # Extract the portion of assignment.name before " - "
    assignment_name = assignment.name.split(" - ")[0]

    print(f"Selected assignment: {assignment_name}")

    # Check that submission assignment exists
    try:
        a_submit = course.get_assignments(search_term=assignment_name + " - " + config["submission_suffix"])[0]
        print(a_submit.name, 'exists.')

        # Get assignment points
        total_point_val = a_submit.points_possible
    except IndexError as e:
        print(a_submit.name, "does not exist. Please check the assignment name.")
        return
    
    # Check that student grading assignment exists
    try:
        a_self = course.get_assignments(search_term=assignment_name + " - " + config["score_suffix"])[0]
        print(a_self.name, 'exists.')
    except IndexError as e:
        print(a_self.name, "does not exist. Please check the assignment name.")
        return
    
    
    # Fetch scores from Canvas
    if args.fetch:

        # Extract problems from quiz questions
        q_probs = course.get_quiz(a_self.quiz_id).get_questions()
        p_point_vals = {q.id:q.points_possible for q in q_probs if config["problem_prefix"] in q.question_name}
        p_names = {q.id:q.question_name for q in q_probs if config["problem_prefix"] in q.question_name}

        # Check for existing scores file
        if os.path.exists(f"{assignment_name}_scores.csv"):
            if args.verbose:
                print(f"Loading existing scores from {assignment_name}_scores.csv")
            df_scores = pd.read_csv(f"{assignment_name}_scores.csv", index_col=0)
            df_scores["checked"] = df_scores["checked"].fillna(False)
        else:
            # Create empty dataframe of student scores
            if args.verbose:
                print(f"Creating empty scores dataframe for {assignment_name}")
            
            p_cols = list(chain.from_iterable([[p + "_s", p + "_i"] for p in p_names.values()]))
            cols = (["name", "hw_id", "grade_id", "checked"] +
                    p_cols + ["student_score", "final_score", "error"])
            df_scores = pd.DataFrame(columns=cols)
            df_scores["checked"] = False

        # Get Check Problem from arguments, or prompt for input
        if not args.check_problem:
            args.check_problem = input('Enter the Check Problem name (e.g. "Problem 3"): ')

        # Get the corresponding problem ID
        check_problem_id = None
        for p_id, p_name in p_names.items():
            if args.check_problem.lower() in p_name.lower():
                check_problem_id = p_id
                break

        if check_problem_id is None:
            print("No matching Check Problem found. Please check the name and try again.")
            return


        # For each student...
        for user in course.get_users(enrollment_type=['student']):

            def log_error(msg):
                if args.verbose:
                    print(f"Error for {user.name}: {msg}")
                df_scores.loc[user.id, "error"] = msg

            if args.verbose:
                print(f"Fetching scores for {user.name}...")

            # Update or create new row for current student
            df_scores.loc[user.id, "name"] = user.name

            # Check whether the student has submitted the assignment
            hw_sub = a_submit.get_submission(user=user.id)
            if hw_sub is None:
                log_error(" * No submission found.")
                continue

            # Check if there was an existing assignment submission
            if pd.notnull(df_scores.loc[user.id, "hw_id"]):
                if hw_sub.id != df_scores.loc[user.id, "hw_id"]:
                    # New submission. Prompt to clear instructor scores
                    if args.verbose:
                        print(f" * New HW submission found")

                    overwrite = args.overwrite
                    if not args.overwrite:  # Prompt for overwrite
                        clear_scores = input(f" * Clear ALL instructor scores for {user.name}? (y/n) ")
                        overwrite = clear_scores.lower() == "y"

                    if overwrite:
                        if args.verbose:
                            print(" * Overwriting instructor scores")

                        # Clear all fields in df_scores ending in "_i"
                        df_scores.loc[user.id, df_scores.columns.str.endswith("_i")] = None

                        # Set CHECKED column to False
                        df_scores.loc[user.id, "checked"] = False

            # Fetch instructor score
            inst_evaluation = a_submit.get_submission(user=user.id)

            if inst_evaluation.grade is not None:
                df_scores.loc[user.id, p_names[check_problem_id] + "_i"] = float(inst_evaluation.grade)
            else:
                log_error(" * No instructor score found.")
            
            # Update submission ID
            df_scores.loc[user.id, "hw_id"] = hw_sub.id

            # Get self grade submission
            grade_sub = a_self.get_submission(user=user.id, include=["submission_history"])

            # Get latest submission
            s_index = argmax([sh['attempt'] for sh in grade_sub.submission_history])
            s_latest = grade_sub.submission_history[s_index]

            if 'submission_data' not in s_latest:
                log_error(" * No student grade submission found.")
                continue

            # Check if grade submission is new
            if pd.notnull(df_scores.loc[user.id, "grade_id"]):
                if s_latest["id"] != df_scores.loc[user.id, "grade_id"]:
                    if args.verbose:
                        print(f" * New student grade submission found.")

                    df_scores.loc[user.id, "checked"] = False

            # Update grade submission ID
            df_scores.loc[user.id, "grade_id"] = s_latest["id"]

            # Get student-submitted scores for each problem
            for q in s_latest["submission_data"]:     # Loop over quiz questions
                if q["question_id"] in p_point_vals:  # If Problem
                    p_name = p_names[q["question_id"]]
                    student_score = float(q["text"])  # Student's entered score
                    df_scores.loc[user.id, p_name + "_s"] = student_score

                    if student_score > p_point_vals[q["question_id"]]:
                        log_error(f"Student entered score greater than maximum for {p_name}.")
                        continue
                    if student_score < 0:
                        log_error(f"Student entered a score less than zero for {p_name}.")
                        continue

        # Calculate total scores
        df_scores = calc_final_scores(df_scores)

        # Save scores to CSV
        df_scores.to_csv(f"{assignment_name}_scores.csv")

    # Enter final grades into Canvas gradebook
    if args.upload:

        # Check that final grade assignment exists. If not prompt to create one.
        try:
            a_final = course.get_assignments(search_term=assignment_name + " - " + config["final_suffix"])[0]
            print(a_final.name, 'exists.')
        except IndexError as e:
            create_final = input(a_final.name, "does not exist. Create it now? (y/n)")
            if create_final.lower() == 'y':
                a_final = course.create_assignment({
                    'name': assignment_name + " - " + config["final_suffix"],
                    'points_possible': total_point_val
                })
                print(a_final.name, 'created. You must publish it on Canvas before proceeding.')
            else:
                print("Exiting.")
            
            return

        # Read scores from CSV
        df_scores = pd.read_csv(f"{assignment_name}_scores.csv", index_col=0)
        df_scores["checked"] = df_scores["checked"].fillna(False)

        # Calculate total scores
        df_scores = calc_final_scores(df_scores)

        # Upload scores for all rows marked "Checked"
        for user_id, row in df_scores[df_scores["checked"]].iterrows():
            if args.verbose:
                print(f"Uploading score for {row['name']}: {row['final_score']}")

            s_final = a_final.get_submission(user_id)
            s_final.edit(submission={'posted_grade': row["final_score"]})

if __name__ == "__main__":
    main()
