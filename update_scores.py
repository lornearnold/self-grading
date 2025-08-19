#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Update Canvas grades for a student-graded assignment."""

import json
import pandas as pd
from numpy import argmax
from itertools import chain
from canvasapi import Canvas
from argparse import ArgumentParser


def main():
    parser = ArgumentParser(description="Update Canvas grades for a student-graded assignment.")
    parser.add_argument("-c", "--course_id", help="Canvas course ID", type=int)
    parser.add_argument("-a", "--assignment_id", help="Canvas assignment ID", type=int)
    parser.add_argument("-f", "--fetch", help="Fetch scores from Canvas", action="store_true")
    parser.add_argument("-u", "--upload", help="Upload scores to Canvas", action="store_true")
    parser.add_argument("-p", "--check_problem", help="Check Problem name (e.g. 'Problem 3')")
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
                    "canvas_url": "https://canvas.yourinstitution.edu",
                    "course_id": 123,
                    "submission_suffix": "submit your work",
                    "score_suffix": "grade your work",
                    "final_suffix": "final grade",
                    "problem_prefix": "Problem"}, f)
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
            a_final = None

    # Get point values of quiz questions corresponding to Problems
    q_probs = course.get_quiz(a_self.quiz_id).get_questions()
    p_point_vals = {q.id:q.points_possible for q in q_probs if config["problem_prefix"] in q.question_name}
    p_names = {q.id:q.question_name for q in q_probs if config["problem_prefix"] in q.question_name}

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

    # Fetch scores from Canvas
    if args.fetch:
        # Create empty dataframe of student scores
        p_cols = list(chain.from_iterable([[p + "_s", p + "_i"] for p in p_names.values()]))
        df_scores = pd.DataFrame(columns=["name", "status"] + p_cols + ["student_score", "final_score"])

        # For each student...
        i = 0
        for user in course.get_users(enrollment_type=['student']):
            if i == 5:
                break
            else:
                i += 1

            def log_error(msg):
                if args.verbose:
                    print(f"Error for {user.name}: {msg}")
                    df_scores.loc[user.id, "status"] = msg

            # Create new row for current student
            df_scores.loc[user.id, "name"] = user.name

            # Get self grade submission history (includes all attempts)
            s = a_self.get_submission(user=user.id, include='submission_history')

            # Get latest submission
            sh_index = argmax([sh['attempt'] for sh in s.submission_history])
            sh_latest = s.submission_history[sh_index]

            if "submission_data" not in sh_latest:
                log_error("No student-submitted grade found.")
                continue

            # Get instructor score
            inst_evaluation = a_submit.get_submission(user=user.id)

            if inst_evaluation.grade is not None:
                df_scores.loc[user.id, p_names[check_problem_id] + "_i"] = float(inst_evaluation.grade)
            else:
                log_error('No instructor grade found for student')

            student_final_score = 0
            final_score = 0

            # Get student-submitted scores for each problem
            for q in sh_latest["submission_data"]:    # Loop over quiz questions
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

                    student_final_score += student_score

                    if q["question_id"] == check_problem_id:
                        final_score += float(inst_evaluation.grade)
                    else:
                        final_score += student_score

            df_scores.loc[user.id, "student_score"] = student_final_score
            df_scores.loc[user.id, "final_score"] = final_score

        # Save scores to CSV
        df_scores.to_csv(f"{assignment_name}_scores.csv")


if __name__ == "__main__":
    main()
