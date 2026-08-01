// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/Target.sol";

contract ForceSend {
    constructor() payable {}
    function go(address payable to) external {
        selfdestruct(to);
    }
}

contract BenignBehaviorTest is Test {
    function test_benign_calls() public {
        Target target = new Target();
        address user = address(0xB0B);

        vm.deal(address(this), 100 ether);
        vm.deal(user, 100 ether);

        emit log_named_uint("bal_before", address(target).balance);

        // seed target with a SMALL amount of ETH only if needed
        new ForceSend{value: 0.1 ether}().go(payable(address(target)));


        {
            uint256 snap = vm.snapshot();

            // -----------------
            // OWNER-ish call
            // -----------------
            uint256 t0_owner = address(target).balance;
            uint256 s0_owner = address(this).balance;

            (bool ok_owner, ) = address(target).call{value: 0.01 ether}(abi.encodeWithSignature("my_func_unchk35(address)", address(this)));

            uint256 t1_owner = address(target).balance;
            uint256 s1_owner = address(this).balance;

            emit log_named_uint("c0_owner", ok_owner ? 1 : 0);
            emit log_named_uint("t0_owner_before", t0_owner);
            emit log_named_uint("t0_owner_after",  t1_owner);
            emit log_named_uint("s0_owner_before", s0_owner);
            emit log_named_uint("s0_owner_after",  s1_owner);

            // -----------------
            // USER call
            // -----------------
            vm.startPrank(user);

            uint256 t0_user = address(target).balance;
            uint256 s0_user = user.balance;

            (bool ok_user, ) = address(target).call{value: 0.01 ether}(abi.encodeWithSignature("my_func_unchk35(address)", address(this)));

            uint256 t1_user = address(target).balance;
            uint256 s1_user = user.balance;

            vm.stopPrank();

            emit log_named_uint("c0_user", ok_user ? 1 : 0);
            emit log_named_uint("t0_user_before", t0_user);
            emit log_named_uint("t0_user_after",  t1_user);
            emit log_named_uint("s0_user_before", s0_user);
            emit log_named_uint("s0_user_after",  s1_user);

            vm.revertTo(snap);
        }

        {
            uint256 snap = vm.snapshot();

            // -----------------
            // OWNER-ish call
            // -----------------
            uint256 t0_owner = address(target).balance;
            uint256 s0_owner = address(this).balance;

            (bool ok_owner, ) = address(target).call{value: 0.01 ether}(abi.encodeWithSignature("deposit()"));

            uint256 t1_owner = address(target).balance;
            uint256 s1_owner = address(this).balance;

            emit log_named_uint("c1_owner", ok_owner ? 1 : 0);
            emit log_named_uint("t1_owner_before", t0_owner);
            emit log_named_uint("t1_owner_after",  t1_owner);
            emit log_named_uint("s1_owner_before", s0_owner);
            emit log_named_uint("s1_owner_after",  s1_owner);

            // -----------------
            // USER call
            // -----------------
            vm.startPrank(user);

            uint256 t0_user = address(target).balance;
            uint256 s0_user = user.balance;

            (bool ok_user, ) = address(target).call{value: 0.01 ether}(abi.encodeWithSignature("deposit()"));

            uint256 t1_user = address(target).balance;
            uint256 s1_user = user.balance;

            vm.stopPrank();

            emit log_named_uint("c1_user", ok_user ? 1 : 0);
            emit log_named_uint("t1_user_before", t0_user);
            emit log_named_uint("t1_user_after",  t1_user);
            emit log_named_uint("s1_user_before", s0_user);
            emit log_named_uint("s1_user_after",  s1_user);

            vm.revertTo(snap);
        }

        emit log_named_uint("bal_after", address(target).balance);
    }
}
